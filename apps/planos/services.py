"""Serviços do plano de ação — o que fecha o ciclo achado → correção (CA-08).

Cinco invariantes que este módulo existe para garantir:

1. **Toda ação nasce de um achado.** Recomendação de apreciação ou item de checklist não
   conforme. Ação manual existe, mas é exceção declarada, nunca o caminho padrão.
2. **Nada duplica na regeneração.** Rodar "gerar ações" duas vezes não cria duas ações
   para a mesma recomendação — a restrição única no banco é o backstop, e o serviço
   respeita o registro existente em vez de tentar sobrescrever.
3. **Responsável e prazo são obrigatórios.** Ação sem responsável nominal é intenção. O
   prazo é SUGERIDO pelo HRN da zona e gravado como decisão de quem responde pela obra.
4. **Não encerra sem evidência.** Foto, nota fiscal, certificado ou laudo. Encerrar sem
   prova é o defeito que o produto existe para eliminar.
5. **A data que vale é a do fato.** Proteção instalada em agosto e registrada em setembro
   recalcula a adequação em agosto. Sem isso a curva de evolução é ficção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.ativos.models import Machine
from apps.checklists.enums import ItemResult
from apps.checklists.models import ItemResultRecord
from apps.clientes.models import Person
from apps.core.enums import AuditAction
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from apps.risco.enums import EstimateKind
from apps.risco.models import Recommendation
from motores.plano import Situacao, classificar_vencimento
from motores.plano.prazo import dias_sugeridos, prazo_sugerido

from .enums import ActionSource, ActionStatus, EvidenceKind
from .models import Action, ActionPlan, DeadlineChange, Evidence


class EncerramentoSemEvidencia(Exception):
    """Regra do produto: ação não encerra sem prova de fechamento."""


class AcaoJaEncerrada(Exception):
    """Ação concluída ou cancelada não volta a ser editada — corrige-se por nova ação."""


class PrazoSemJustificativa(Exception):
    """Repactuar prazo sem dizer por quê transformaria o plano em ficção."""


# ------------------------------------------------------------------------------- plano

@transaction.atomic
def abrir_plano(*, machine: Machine, actor: User | None = None, title: str = "") -> ActionPlan:
    """Um plano por máquina. Chamar de novo devolve o existente, não cria outro."""
    existente = ActionPlan.objects.filter(machine=machine).first()
    if existente is not None:
        return existente
    sequencia = ActionPlan.objects.count() + 1
    plano = ActionPlan.objects.create(
        tenant_id=require_tenant(), machine=machine,
        number=f"PA-{timezone.now():%Y}-{sequencia:04d}",
        title=title or f"Plano de ação · {machine.name}", created_by=actor,
    )
    registrar_auditoria(
        action=AuditAction.CREATE, entity=plano, actor=actor,
        new_value={"plano": plano.number, "maquina": machine.name},
    )
    return plano


def _proximo_codigo() -> str:
    return f"A-{Action.objects.count() + 1:04d}"


def _hrn_da_zona(hazard) -> Decimal | None:  # noqa: ANN001
    """Prazo nasce do risco. Sem residual, usa o inicial — é o pior caso conhecido."""
    if hazard is None:
        return None
    residual = hazard.estimates.filter(kind=EstimateKind.RESIDUAL).first()
    if residual is not None:
        return residual.product
    inicial = hazard.estimates.filter(kind=EstimateKind.INITIAL).first()
    return inicial.product if inicial else None


# ------------------------------------------------------------------------------- ações

@transaction.atomic
def criar_acao(
    *, plan: ActionPlan, text: str, owner: Person, source: str = ActionSource.MANUAL,
    recommendation: Recommendation | None = None, item_result: ItemResultRecord | None = None,
    hazard=None, deadline: date | None = None, deadline_rationale: str = "",  # noqa: ANN001
    blocking: bool = False, estimated_cost: Decimal | None = None, actor: User | None = None,
) -> Action:
    """Cria uma ação. O prazo é sugerido pelo HRN quando não vem informado."""
    zona = hazard or getattr(recommendation, "hazard", None)
    hrn = _hrn_da_zona(zona)
    sugeridos = dias_sugeridos(hrn)
    prazo = deadline or prazo_sugerido(hrn) or (timezone.localdate() + timezone.timedelta(days=30))

    acao = Action(
        tenant_id=require_tenant(), plan=plan, code=_proximo_codigo(), source=source,
        recommendation=recommendation, item_result=item_result, hazard=zona, text=text,
        owner=owner, deadline=prazo, suggested_days=sugeridos,
        deadline_rationale=deadline_rationale, blocking=blocking,
        estimated_cost=estimated_cost, created_by=actor,
    )
    acao.full_clean(exclude=["code"])
    acao.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=acao, actor=actor,
        new_value={
            "acao": acao.code, "responsavel": owner.name, "prazo": str(prazo),
            "origem": source, "hrn_da_zona": str(hrn) if hrn is not None else None,
        },
    )
    return acao


@transaction.atomic
def gerar_acoes_de_nao_conformidade(
    *, machine: Machine, owner: Person | None = None, actor: User | None = None
) -> list[Action]:
    """Converte todo achado da máquina em ação. Idempotente por construção.

    O responsável padrão é o engenheiro do projeto — nunca "a definir": ação sem dono
    nominal é exatamente o que o plano existe para impedir.
    """
    dono = owner or _responsavel_padrao(machine)
    if dono is None:
        raise ValueError(
            "Nenhum responsável informado e a máquina não tem engenheiro de projeto vinculado. "
            "Ação sem responsável nominal não é ação."
        )
    plano = abrir_plano(machine=machine, actor=actor)
    criadas: list[Action] = []

    medidas = (
        Recommendation.objects.filter(hazard__machine=machine, actions__isnull=True)
        .select_related("hazard")
        .prefetch_related("hazard__estimates")
    )
    for medida in medidas:
        # blocking=False de propósito. A ação NASCE da recomendação do documento; marcá-la
        # como bloqueante impediria a publicação do próprio documento que a recomendou —
        # impasse circular. Bloqueante é marca deliberada, aplicada depois (marcar_bloqueante).
        criadas.append(
            criar_acao(
                plan=plano, text=medida.text, owner=dono,
                source=ActionSource.RECOMMENDATION, recommendation=medida,
                hazard=medida.hazard, actor=actor,
            )
        )

    itens = (
        ItemResultRecord.objects.filter(
            assessment__machine=machine,
            result__in=[ItemResult.NON_COMPLIANT, ItemResult.PARTIAL],
            actions__isnull=True,
        )
        .select_related("library_item")
    )
    for item in itens:
        criadas.append(
            criar_acao(
                plan=plano,
                text=f"Adequar: {item.library_item.statement}",
                owner=dono, source=ActionSource.CHECKLIST, item_result=item, actor=actor,
            )
        )
    return criadas


def _responsavel_padrao(machine: Machine) -> Person | None:
    projeto = getattr(machine, "project", None)
    return getattr(projeto, "engineer", None)


@transaction.atomic
def marcar_bloqueante(
    *, action: Action, reason: str, actor: User | None = None
) -> Action:
    """Marca a ação como retentora de publicação.

    Ato DELIBERADO, nunca automático: uma ação gerada a partir da recomendação de um
    documento não pode bloquear a publicação desse documento — seria impasse circular.
    O uso legítimo é reter a PRÓXIMA emissão enquanto um risco crítico segue aberto.
    """
    _recusar_se_encerrada(action)
    if not reason.strip():
        raise ValueError(
            "Marcar ação como bloqueante exige motivo: alguém vai descobrir esse bloqueio "
            "na hora de emitir e precisa saber por quê."
        )
    action.blocking = True
    action.deadline_rationale = (
        f"{action.deadline_rationale}\n[bloqueante] {reason}".strip()
    )
    action.save(update_fields=["blocking", "deadline_rationale", "updated_at"])
    registrar_auditoria(action=AuditAction.UPDATE, entity=action, actor=actor,
                        new_value={"bloqueante": True, "motivo": reason[:200]})
    return action


@transaction.atomic
def iniciar_acao(*, action: Action, actor: User | None = None) -> Action:
    _recusar_se_encerrada(action)
    action.status = ActionStatus.IN_PROGRESS
    action.save(update_fields=["status", "updated_at"])
    registrar_auditoria(action=AuditAction.UPDATE, entity=action, actor=actor,
                        new_value={"status": ActionStatus.IN_PROGRESS})
    return action


@transaction.atomic
def anexar_evidencia(
    *, action: Action, file_key: str, kind: str = EvidenceKind.PHOTO, caption: str = "",
    sha256: str = "", occurred_on: date | None = None, bytes_size: int | None = None,
    actor: User | None = None,
) -> Evidence:
    """Registra a prova. O binário já subiu ao armazenamento; aqui fica o hash."""
    evidencia = Evidence.objects.create(
        tenant_id=require_tenant(), action=action, kind=kind, file_key=file_key,
        sha256=sha256, caption=caption, occurred_on=occurred_on, bytes_size=bytes_size,
        created_by=actor,
    )
    registrar_auditoria(
        action=AuditAction.CREATE, entity=evidencia, actor=actor,
        new_value={"acao": action.code, "tipo": kind, "chave": file_key},
    )
    return evidencia


@transaction.atomic
def concluir_acao(
    *, action: Action, completed_on: date | None = None, actor: User | None = None
) -> Action:
    """Encerra a ação. RECUSA sem evidência anexada — é a regra central do plano."""
    _recusar_se_encerrada(action)
    if not action.evidences.exists():
        raise EncerramentoSemEvidencia(
            f"A ação {action.code} não pode ser encerrada sem evidência. "
            "Anexe foto, nota fiscal, certificado ou laudo que comprove a execução."
        )
    # Data do fato: a da evidência mais antiga, não a de hoje.
    do_fato = completed_on or _data_do_fato(action)
    action.status = ActionStatus.DONE
    action.completed_on = do_fato
    action.save(update_fields=["status", "completed_on", "updated_at"])
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=action, actor=actor,
        new_value={
            "status": ActionStatus.DONE, "concluida_em": str(do_fato),
            "evidencias": action.evidences.count(),
        },
    )
    return action


def _data_do_fato(action: Action) -> date:
    datas = [e.occurred_on for e in action.evidences.all() if e.occurred_on]
    return min(datas) if datas else timezone.localdate()


@transaction.atomic
def cancelar_acao(*, action: Action, reason: str, actor: User | None = None) -> Action:
    """Cancelar exige motivo e NÃO remove a ação do denominador da adequação."""
    _recusar_se_encerrada(action)
    if not reason.strip():
        raise ValueError("Cancelamento exige motivo — ação cancelada em silêncio é ação perdida.")
    action.status = ActionStatus.CANCELLED
    action.cancel_reason = reason
    action.save(update_fields=["status", "cancel_reason", "updated_at"])
    registrar_auditoria(action=AuditAction.UPDATE, entity=action, actor=actor,
                        new_value={"status": ActionStatus.CANCELLED, "motivo": reason[:200]})
    return action


@transaction.atomic
def repactuar_prazo(
    *, action: Action, novo_prazo: date, reason: str, actor: User | None = None
) -> DeadlineChange:
    """Muda o prazo deixando rastro. Sem histórico, tudo aparece 'no prazo' no fim do ano."""
    _recusar_se_encerrada(action)
    if not reason.strip():
        raise PrazoSemJustificativa(
            "Repactuar prazo exige justificativa. Prazo empurrado sem motivo registrado "
            "transforma o plano de ação em ficção."
        )
    anterior = action.deadline
    mudanca = DeadlineChange.objects.create(
        tenant_id=require_tenant(), action=action, previous=anterior, current=novo_prazo,
        reason=reason, created_by=actor,
    )
    action.deadline = novo_prazo
    action.save(update_fields=["deadline", "updated_at"])
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=action, actor=actor,
        old_value={"prazo": str(anterior)},
        new_value={"prazo": str(novo_prazo), "justificativa": reason[:200],
                   "dias_empurrados": mudanca.dias_empurrados},
    )
    return mudanca


def _recusar_se_encerrada(action: Action) -> None:
    if action.status in (ActionStatus.DONE, ActionStatus.CANCELLED):
        raise AcaoJaEncerrada(
            f"A ação {action.code} está {action.get_status_display().lower()} e não pode ser "
            "alterada. Registre uma nova ação em vez de reabrir o histórico."
        )


def situacao_de(action: Action, *, hoje: date | None = None) -> Situacao:
    """Situação DERIVADA — nunca gravada em coluna."""
    return classificar_vencimento(
        prazo=action.deadline,
        concluida_em=action.completed_on,
        cancelada=action.status == ActionStatus.CANCELLED,
        iniciada=action.status == ActionStatus.IN_PROGRESS,
        hoje=hoje,
    ).situacao
