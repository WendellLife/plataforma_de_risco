"""Consultas de campo. Sempre com escopo de tenant."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.ativos.enums import MachineStatus
from apps.ativos.models import Machine
from apps.checklists.enums import AssessmentStatus
from apps.checklists.models import Assessment, LibraryItem

from .models import Device, SyncBatch


def pacote_offline(*, operator) -> dict[str, Any]:  # noqa: ANN001
    """Tudo o que o aparelho precisa para trabalhar sem rede.

    Inclui os ENUNCIADOS da biblioteca porque o app de campo não pode inventar texto
    normativo offline — ele referencia a biblioteca, exatamente como o documento.
    """
    aplicacoes = (
        Assessment.objects.filter(
            status=AssessmentStatus.DRAFT, collected_by=operator,
            machine__status=MachineStatus.ACTIVE,
        )
        .select_related("machine", "machine__client", "machine__machine_type")
        .prefetch_related("results__library_item")
    )
    normas = sorted({a.standard for a in aplicacoes})
    itens = LibraryItem.objects.filter(standard__in=normas, retired_at__isnull=True)
    return {
        "inspections": [
            {
                "assessment": str(a.public_uuid),
                "machine": str(a.machine.public_uuid),
                "machine_name": a.machine.name,
                "client": a.machine.client.legal_name,
                "standard": a.standard,
                "library_base_count": a.library_base_count,
                "answered": [r.library_item.library_key for r in a.results.all()],
            }
            for a in aplicacoes
        ],
        "library": [
            {
                "library_key": i.library_key, "standard": i.standard, "group": i.group_name,
                "statement": i.statement, "help_text": i.help_text, "annex": i.annex,
                "requires_evidence": i.requires_evidence, "version": i.version,
            }
            for i in itens
        ],
        "photo_slots": ["overview", "finding", "nameplate", "device", "lockout"],
    }


def lotes(*, status: str | None = None) -> QuerySet[SyncBatch]:
    qs = SyncBatch.objects.select_related("device", "device__operator").prefetch_related("records")
    return qs.filter(status=status) if status else qs


def aparelhos() -> QuerySet[Device]:
    return Device.objects.select_related("operator").order_by("-paired_at")


def indicadores_de_campo() -> dict[str, Any]:
    total = SyncBatch.objects.count()
    com_conflito = SyncBatch.objects.filter(conflict_count__gt=0).count()
    return {
        "lotes": total,
        "conflitos": com_conflito,
        "aparelhos_ativos": Device.objects.filter(status="active").count(),
        "maquinas_ativas": Machine.objects.filter(status=MachineStatus.ACTIVE).count(),
    }
