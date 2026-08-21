"""Emissão em lote (CA-10) — cem máquinas sem transformar a espera em fé.

Quatro invariantes:

1. **Triagem antes da fila.** `planejar_lote` calcula e devolve o plano com prontas e
   recusadas ANTES de o usuário confirmar. Ninguém enfileira 100 e descobre depois que 40
   estavam bloqueadas.
2. **O lote não é transação única.** Cada máquina publica em sua própria transação. Falha
   na 47ª não desfaz as 46 anteriores — cada versão publicada é imutável por definição.
3. **A regra de permissão não afrouxa no lote.** Emissão em massa passa exatamente pelo
   mesmo `publicar()` da emissão individual, com o mesmo verificador e a mesma exigência
   de engenheiro. Um atalho aqui seria a maneira mais fácil de furar o produto.
4. **Registro persistente.** Quem pediu pode fechar o navegador e voltar depois: o lote e
   cada item guardam resultado, regra que impediu e hash do que saiu.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.ativos.enums import MachineStatus
from apps.ativos.models import Machine
from apps.clientes.models import Client
from apps.core.enums import AuditAction, UserRole
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from apps.documentos.enums import DocumentStatus
from apps.documentos.models import Document
from apps.documentos.services import (
    PermissaoDePublicacao,
    PublicacaoBloqueada,
    criar_documento,
    montar,
    publicar,
    sincronizar_bloqueios,
)
from motores.documento import template as template_do_catalogo
from motores.lote import LIMITE_POR_LOTE, Plano, planejar

from .models import BatchItemStatus, BatchStatus, IssueBatch, IssueBatchItem


class LoteVazio(Exception):
    """Nenhuma máquina elegível. Enfileirar nada é pior que recusar com motivo."""


def _maquinas(client: Client | None) -> list[Machine]:
    qs = Machine.objects.filter(status=MachineStatus.ACTIVE).select_related(
        "client", "machine_type", "project", "project__engineer"
    )
    if client is not None:
        qs = qs.filter(client=client)
    return list(qs.order_by("name"))


def planejar_lote(
    *, template_code: str, client: Client | None = None, actor: User | None = None
) -> Plano:
    """Triagem de verdade: roda o verificador em cada máquina antes de prometer nada.

    É a parte caramente honesta desta função — ela custa tempo justamente para que o
    usuário não descubra os bloqueios depois de esperar meia hora.
    """
    template = template_do_catalogo(template_code)
    candidatas: list[dict[str, object]] = []

    for maquina in _maquinas(client):
        registro: dict[str, object] = {
            "uuid": str(maquina.public_uuid),
            "label": maquina.name,
            "template_implementado": template.implementado,
        }
        if not template.implementado:
            candidatas.append(registro)
            continue

        documento = Document.objects.filter(
            machine=maquina, template_code=template_code
        ).first()
        if documento is not None and documento.status == DocumentStatus.PUBLISHED:
            registro["ja_publicada"] = True
            candidatas.append(registro)
            continue

        # Sem documento ainda: monta o contexto direto da máquina para triar sem criar nada.
        if documento is None:
            documento = criar_documento(
                machine=maquina, template_code=template_code, actor=actor
            )
        contexto = montar(documento=documento)
        sincronizar_bloqueios(documento=documento, contexto=contexto)
        if contexto.bloqueios:
            registro["bloqueios"] = sorted({v.regra for v in contexto.bloqueios})
            registro["detalhe"] = contexto.bloqueios[0].mensagem
        candidatas.append(registro)

    return planejar(template_code, candidatas)


def abrir_lote(
    *, template_code: str, plano: Plano, actor: User, client: Client | None = None
) -> IssueBatch:
    """Grava o lote e seus itens a partir do plano já mostrado ao usuário.

    As recusas ficam FORA da transação de gravação: dentro dela, o raise desfaria a
    própria trilha de auditoria que registra a tentativa negada.
    """
    if plano.vazio:
        raise LoteVazio(
            f"Nenhuma máquina elegível para {template_code}. "
            f"{len(plano.recusadas)} recusada(s) — corrija os bloqueios e planeje de novo."
        )
    template = template_do_catalogo(template_code)
    if template.exige_engenheiro and actor.role != UserRole.ENGINEER:
        registrar_auditoria(
            action=AuditAction.PERMISSION_DENIED, entity=None,
            entity_table=IssueBatch._meta.db_table, actor=actor,
            new_value={"motivo": "perfil não emite peça de responsabilidade técnica em lote",
                       "template": template_code},
        )
        raise PermissaoDePublicacao(
            f"{template.nome} é peça de responsabilidade técnica — somente engenheiro emite, "
            "individualmente ou em lote."
        )

    with transaction.atomic():
        return _gravar_lote(
            template_code=template_code, plano=plano, actor=actor, client=client
        )


def _gravar_lote(
    *, template_code: str, plano: Plano, actor: User, client: Client | None = None
) -> IssueBatch:
    sequencia = IssueBatch.objects.count() + 1
    lote = IssueBatch.objects.create(
        tenant_id=require_tenant(),
        number=f"LT-{timezone.now():%Y}-{sequencia:04d}",
        template_code=template_code, client=client,
        requested_count=len(plano.prontas), skipped_count=len(plano.recusadas),
        plan_snapshot=plano.as_dict(), created_by=actor,
    )

    por_uuid = {str(m.public_uuid): m for m in _maquinas(client)}
    for item in plano.itens:
        maquina = por_uuid.get(item.machine_uuid)
        if maquina is None:
            continue
        IssueBatchItem.objects.create(
            tenant_id=require_tenant(), batch=lote, machine=maquina,
            status=BatchItemStatus.QUEUED if item.entra else BatchItemStatus.SKIPPED,
            rules=list(item.regras), message="" if item.entra else item.rotulo,
            created_by=actor,
        )

    registrar_auditoria(
        action=AuditAction.CREATE, entity=lote, actor=actor,
        new_value={"lote": lote.number, "template": template_code,
                   "solicitados": lote.requested_count, "recusados": lote.skipped_count},
    )
    return lote


def executar_lote(*, batch_id: int, actor_id: int) -> IssueBatch:
    """Publica item por item. Cada um em sua própria transação — sem tudo-ou-nada.

    Chamado pela fila "lotes". Roda também em linha nos testes, sem worker.
    """
    lote = IssueBatch.sem_escopo.get(pk=batch_id)
    actor = User.objects.get(pk=actor_id)

    lote.status = BatchStatus.RUNNING
    lote.started_at = lote.started_at or timezone.now()
    lote.save(update_fields=["status", "started_at", "updated_at"])

    fila = lote.items.filter(status=BatchItemStatus.QUEUED).select_related("machine")
    for item in fila:
        _emitir_item(lote=lote, item=item, actor=actor)

    lote.refresh_from_db()
    lote.published_count = lote.items.filter(status=BatchItemStatus.PUBLISHED).count()
    lote.failed_count = lote.items.filter(status=BatchItemStatus.FAILED).count()
    lote.status = BatchStatus.PARTIAL if lote.failed_count else BatchStatus.DONE
    lote.finished_at = timezone.now()
    lote.save(
        update_fields=["published_count", "failed_count", "status", "finished_at", "updated_at"]
    )
    registrar_auditoria(
        action=AuditAction.PUBLISH, entity=lote, actor=actor,
        new_value={"lote": lote.number, "publicados": lote.published_count,
                   "falhos": lote.failed_count, "minutos": lote.duracao_minutos},
        tenant_id=lote.tenant_id,
    )
    return lote


def _emitir_item(*, lote: IssueBatch, item: IssueBatchItem, actor: User) -> None:
    """Uma emissão. O MESMO publicar() da emissão individual — sem atalho de lote."""
    try:
        with transaction.atomic():
            documento = Document.objects.filter(
                machine=item.machine, template_code=lote.template_code
            ).first() or criar_documento(
                machine=item.machine, template_code=lote.template_code, actor=actor
            )
            versao = publicar(documento=documento, actor=actor)
            item.document = documento
            item.version_number = versao.number
            item.content_hash = versao.content_hash
            item.status = BatchItemStatus.PUBLISHED
            item.message = ""
            item.save(
                update_fields=[
                    "document", "version_number", "content_hash", "status", "message",
                    "updated_at",
                ]
            )
    except PublicacaoBloqueada as recusa:
        # Bloqueio que apareceu entre a triagem e a execução: alguém mudou o cadastro.
        _falhar(item, regras=sorted({v.regra for v in recusa.violacoes}),
                mensagem=recusa.violacoes[0].mensagem if recusa.violacoes else str(recusa))
    except PermissaoDePublicacao as erro:
        _falhar(item, regras=["AD-05"], mensagem=str(erro))
    except Exception as erro:  # noqa: BLE001 - a falha de um item não derruba o lote
        _falhar(item, regras=[], mensagem=f"{type(erro).__name__}: {erro}")


def _falhar(item: IssueBatchItem, *, regras: list[str], mensagem: str) -> None:
    item.status = BatchItemStatus.FAILED
    item.rules = regras
    item.message = mensagem[:500]
    item.save(update_fields=["status", "rules", "message", "updated_at"])


@transaction.atomic
def cancelar_lote(*, batch: IssueBatch, actor: User | None = None) -> IssueBatch:
    """Cancela o que ainda não saiu. O que já foi publicado permanece — versão é imutável."""
    pendentes = batch.items.filter(status=BatchItemStatus.QUEUED).update(
        status=BatchItemStatus.SKIPPED, message="Lote cancelado antes da emissão."
    )
    batch.status = BatchStatus.CANCELLED
    batch.finished_at = timezone.now()
    batch.save(update_fields=["status", "finished_at", "updated_at"])
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=batch, actor=actor,
        new_value={"status": BatchStatus.CANCELLED, "cancelados": pendentes,
                   "publicados_mantidos": batch.published_count},
    )
    return batch


def limite() -> int:
    return LIMITE_POR_LOTE
