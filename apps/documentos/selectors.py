"""Extração do escopo de emissão.

Fronteira entre ORM e motor: aqui se lê o banco, ali se decide. O motor de documentos
recebe apenas dicionários — é o que permite testá-lo sem banco e reaproveitá-lo na
emissão em lote (Sprint 7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Prefetch, Q

from apps.ativos.models import Component, EnergySource, Machine
from apps.checklists.enums import AssessmentStatus, ItemResult, Standard
from apps.checklists.models import Assessment, ItemResultRecord, LibraryItem
from apps.risco.enums import EstimateKind
from apps.risco.models import Hazard
from motores.conformidade import Resposta, ResultadoItem, calcular
from motores.documento import rotulo_faixa

from .models import Document

NORMAS_DE_REFERENCIA: tuple[tuple[str, str], ...] = (
    ("NR-12", "Segurança no trabalho em máquinas e equipamentos"),
    ("NR-10", "Segurança em instalações e serviços em eletricidade"),
    ("ABNT NBR ISO 12100", "Segurança de máquinas — princípios gerais de projeto"),
    ("ABNT NBR ISO 13849-1", "Partes de sistemas de comando relacionadas à segurança"),
    ("ABNT NBR ISO 14119", "Dispositivos de interbloqueio associados a proteções"),
    ("ABNT NBR ISO 13857", "Distâncias de segurança para impedir o acesso a zonas de perigo"),
    ("ABNT NBR 14153", "Dispositivos de segurança — princípios para projeto"),
)


def _maquina_completa(uuid: str) -> Machine:
    return (
        Machine.objects.select_related(
            "client", "org_unit", "machine_type", "project", "project__engineer"
        )
        .prefetch_related(
            Prefetch("energy_sources", queryset=EnergySource.objects.select_related("lockout_point")),
            Prefetch("components", queryset=Component.objects.all()),
            Prefetch(
                "hazards",
                queryset=Hazard.objects.prefetch_related(
                    "estimates", "recommendations", "recommendations__standard_reference"
                ).select_related("safety_category"),
            ),
        )
        .get(public_uuid=uuid)
    )


def _identificacao(m: Machine) -> dict[str, Any]:
    cliente = m.client
    projeto = m.project
    engenheiro = getattr(projeto, "engineer", None)
    endereco = cliente.address or {}
    return {
        "cliente": {
            "razao_social": cliente.legal_name,
            "cnpj": cliente.tax_id,
            "cnae": cliente.cnae,
            "municipio": endereco.get("municipio", ""),
            "uf": endereco.get("uf", ""),
            "contato": (cliente.contact or {}).get("nome", ""),
        },
        "unidade": m.org_unit.caminho if m.org_unit else "",
        "maquina": {
            "uuid": str(m.public_uuid),
            "identificacao": m.name,
            "tipo": m.machine_type.name if m.machine_type else "não definido",
            "fabricante": m.manufacturer,
            "modelo": m.model,
            "serie": m.serial_number,
            "patrimonio": m.asset_tag,
            "ano": m.year,
            "capacidade": m.capacity,
            "peso": m.weight_kg,
            "anexos": (m.machine_type.nr12_annexes if m.machine_type else []) or [],
        },
        "projeto": {
            "numero": projeto.number if projeto else "",
            "nome": projeto.name if projeto else "",
            "art": projeto.art_number if projeto else "",
        },
        "responsavel": {
            "uuid": str(engenheiro.public_uuid) if engenheiro else "",
            "nome": engenheiro.name if engenheiro else "",
            "titulo": engenheiro.professional_title if engenheiro else "",
            "registro": engenheiro.registro_completo if engenheiro else "",
        },
    }


def _riscos(m: Machine) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    for h in m.hazards.all():
        estimativas = {e.kind: e for e in h.estimates.all()}
        inicial = estimativas.get(EstimateKind.INITIAL)
        residual = estimativas.get(EstimateKind.RESIDUAL)
        cat = getattr(h, "safety_category", None)
        saida.append({
            "uuid": str(h.public_uuid),
            "rotulo": h.rotulo,
            "zona": h.zone,
            "titulo": h.title,
            "descricao": h.description,
            "tipo": h.get_iso12100_type_display(),
            "fase": h.get_lifecycle_phase_display(),
            "tarefa": h.task,
            "medidas_existentes": h.existing_measures,
            "fatores_inicial": _fatores(inicial),
            "hrn_inicial": inicial.product if inicial else None,
            "faixa_inicial": inicial.band if inicial else "",
            "rotulo_inicial": rotulo_faixa(inicial.band) if inicial else "não estimado",
            "fatores_residual": _fatores(residual),
            "hrn_residual": residual.product if residual else None,
            "faixa_residual": residual.band if residual else "",
            "rotulo_residual": rotulo_faixa(residual.band) if residual else "não reestimado",
            "categoria": f"Cat. {cat.get_category_display()} · PLr {cat.get_plr_display()}" if cat else "",
            "justificativa_categoria": cat.rationale if cat else "",
            "medidas": [
                {
                    "texto": r.text,
                    "etapa": r.get_iso12100_step_display(),
                    "dispositivo": r.device,
                    "prazo": r.deadline_days,
                    "referencia": r.standard_reference.library_key if r.standard_reference else "",
                }
                for r in h.recommendations.all()
            ],
        })
    return saida


def _fatores(estimativa: Any) -> dict[str, Any]:
    if estimativa is None:
        return {}
    return {
        "lo": estimativa.lo, "fe": estimativa.fe, "dph": estimativa.dph, "np": estimativa.np,
        "versao": estimativa.method_version,
    }


def _conformidade(m: Machine) -> dict[str, Any] | None:
    """Índice do checklist mais recente encerrado — dois denominadores, sempre."""
    avaliacao = (
        Assessment.objects.filter(machine=m, status=AssessmentStatus.CLOSED)
        .order_by("-closed_at", "-created_at")
        .first()
    )
    if avaliacao is None:
        return None
    respostas_db = list(
        ItemResultRecord.objects.filter(assessment=avaliacao).select_related("library_item")
    )
    respostas = [
        Resposta(
            library_key=r.library_item.library_key,
            resultado=ResultadoItem(r.result),
            justificativa=r.justification,
        )
        for r in respostas_db
    ]
    resultado = calcular(respostas, base_fixa=avaliacao.library_base_count)
    grupos: dict[str, dict[str, int]] = {}
    for r in respostas_db:
        g = grupos.setdefault(
            r.library_item.group_name or "Sem agrupamento",
            {"conformes": 0, "nao_conformes": 0, "parciais": 0, "nao_aplicaveis": 0},
        )
        chave = {
            ItemResult.COMPLIANT: "conformes",
            ItemResult.NON_COMPLIANT: "nao_conformes",
            ItemResult.PARTIAL: "parciais",
            ItemResult.NOT_APPLICABLE: "nao_aplicaveis",
        }[ItemResult(r.result)]
        g[chave] += 1
    return {
        "norma": avaliacao.get_standard_display(),
        "uuid": str(avaliacao.public_uuid),
        "encerrado_em": avaliacao.closed_at,
        "base_fixa": resultado.base_fixa,
        "avaliados": resultado.avaliados,
        "conformes": resultado.conformes,
        "nao_conformes": resultado.nao_conformes,
        "nao_aplicaveis": resultado.nao_aplicaveis,
        "percentual_base_fixa": resultado.percentual_base_fixa,
        "percentual_avaliados": resultado.percentual_avaliados,
        "grupos": [{"nome": k, **v} for k, v in sorted(grupos.items())],
        "itens_nao_conformes": [
            {
                "library_key": r.library_item.library_key,
                "grupo": r.library_item.group_name,
                "enunciado": r.library_item.statement,
                "observacao": r.note,
                "resultado": r.get_result_display(),
            }
            for r in respostas_db
            if r.result in {ItemResult.NON_COMPLIANT, ItemResult.PARTIAL}
        ],
        "itens_nao_aplicaveis": [
            {
                "library_key": r.library_item.library_key,
                "enunciado": r.library_item.statement,
                "justificativa": r.justification,
            }
            for r in respostas_db
            if r.result == ItemResult.NOT_APPLICABLE
        ],
    }


def _checklists_abertos(m: Machine) -> list[dict[str, Any]]:
    abertos = (
        Assessment.objects.filter(machine=m)
        .exclude(status=AssessmentStatus.CLOSED)
        .annotate(respondidos=Count("results"))
    )
    return [
        {
            "uuid": str(a.public_uuid),
            "norma": a.get_standard_display(),
            "situacao": a.get_status_display(),
            "pendentes": max(a.library_base_count - a.respondidos, 0),
        }
        for a in abertos
    ]


def _itens_na_sem_justificativa(m: Machine) -> list[dict[str, Any]]:
    """Só ocorre em dado importado do acervo legado — a constraint barra dado novo (D-18)."""
    itens = (
        ItemResultRecord.objects.filter(
            assessment__machine=m, result=ItemResult.NOT_APPLICABLE, justification=""
        )
        .select_related("library_item", "assessment")
    )
    return [
        {
            "uuid": str(i.public_uuid),
            "library_key": i.library_item.library_key,
            "assessment_uuid": str(i.assessment.public_uuid),
        }
        for i in itens
    ]


def escopo_da_maquina(uuid: str) -> dict[str, Any]:
    """Escopo completo consumido por build_context — dados + insumos do verificador."""
    m = _maquina_completa(uuid)
    ident = _identificacao(m)
    riscos = _riscos(m)
    hoje = date.today()
    return {
        "machine_uuid": str(m.public_uuid),
        "project_uuid": str(m.project.public_uuid) if m.project else "",
        "identificacao": ident,
        "responsavel": ident["responsavel"],
        "art": ident["projeto"]["art"],
        "maquina_sem_tipo": m.machine_type_id is None,
        "limites": [{"nome": k, "valor": v} for k, v in (m.limits or {}).items()],
        "normas": [{"codigo": c, "titulo": t} for c, t in NORMAS_DE_REFERENCIA],
        "fontes": [
            {
                "uuid": str(f.public_uuid),
                "tipo": f.get_kind_display(),
                "magnitude": f.magnitude,
                "unidade": f.unit,
                "observacao": f.notes,
                "ponto": f.lockout_point.identifier if f.lockout_point else "",
                "local": f.lockout_point.location if f.lockout_point else "",
                "dispositivo": f.lockout_point.device if f.lockout_point else "",
                "procedimento": f.lockout_point.procedure_text if f.lockout_point else "",
                "bloqueavel": f.lockout_point_id is not None,
            }
            for f in m.energy_sources.all()
        ],
        "fontes_sem_bloqueio": [
            {"uuid": str(f.public_uuid), "rotulo": f.rotulo}
            for f in m.energy_sources.all()
            if f.lockout_point_id is None
        ],
        "componentes": [
            {
                "uuid": str(c.public_uuid),
                "rotulo": str(c),
                "dispositivo": c.kind,
                "fabricante": c.manufacturer,
                "modelo": c.model,
                "certificado": c.certificate_number,
                "validade": c.certificate_valid_until,
                "vencido": bool(c.certificate_valid_until and c.certificate_valid_until < hoje),
            }
            for c in m.components.all()
        ],
        "certificados_vencidos": [
            {
                "uuid": str(c.public_uuid), "rotulo": str(c),
                "certificado": c.certificate_number or "sem número",
                "validade": c.certificate_valid_until.strftime("%d/%m/%Y"),
            }
            for c in m.components.all()
            if c.certificate_valid_until and c.certificate_valid_until < hoje
        ],
        "riscos": riscos,
        "riscos_sem_residual": [
            {"uuid": r["uuid"], "rotulo": r["rotulo"]}
            for r in riscos
            if r["medidas"] and not r["faixa_residual"]
        ],
        "conformidade": _conformidade(m),
        "checklists_abertos": _checklists_abertos(m),
        "itens_na_sem_justificativa": _itens_na_sem_justificativa(m),
        "fotos": [
            {"slot": p.get_slot_display(), "legenda": p.caption, "chave": p.file_key}
            for p in m.photos.all()
        ],
    }


def documentos(*, machine_uuid: str | None = None, status: str | None = None):  # noqa: ANN201
    qs = (
        Document.objects.select_related("machine", "machine__client", "current_version")
        .annotate(
            n_bloqueios=Count(
                "blocks", filter=Q(blocks__resolved_at__isnull=True, blocks__severity="block"),
                distinct=True,
            )
        )
        .order_by("-created_at")
    )
    if machine_uuid:
        qs = qs.filter(machine__public_uuid=machine_uuid)
    if status:
        qs = qs.filter(status=status)
    return qs


def base_normativa(norma: str = Standard.NR12) -> int:
    """Tamanho da base fixa vigente — denominador comparável entre máquinas."""
    return LibraryItem.objects.filter(standard=norma, retired_at__isnull=True).count()


def indicadores_de_emissao() -> dict[str, Any]:
    from .enums import DocumentStatus

    base = Document.objects.all()
    return {
        "publicados": base.filter(status=DocumentStatus.PUBLISHED).count(),
        "bloqueados": base.filter(status=DocumentStatus.BLOCKED).count(),
        "rascunhos": base.filter(status=DocumentStatus.DRAFT).count(),
        "conversao": _pct(base.filter(status=DocumentStatus.PUBLISHED).count(), base.count()),
    }


def _pct(parte: int, total: int) -> Decimal:
    if not total:
        return Decimal("0.0")
    return (Decimal(parte) / Decimal(total) * 100).quantize(Decimal("0.1"))
