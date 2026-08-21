"""Consultas de lote. Sempre com escopo de tenant."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from motores.lote import progresso

from .models import BatchItemStatus, IssueBatch


def lotes() -> QuerySet[IssueBatch]:
    return IssueBatch.objects.select_related("client").prefetch_related("items")


def detalhe(batch: IssueBatch) -> dict[str, Any]:
    itens = list(batch.items.select_related("machine", "document").all())
    p = progresso(
        total=batch.requested_count,
        publicados=sum(1 for i in itens if i.status == BatchItemStatus.PUBLISHED),
        falhos=sum(1 for i in itens if i.status == BatchItemStatus.FAILED),
    )
    return {
        "lote": batch,
        "progresso": p,
        "publicados": [i for i in itens if i.status == BatchItemStatus.PUBLISHED],
        "falhos": [i for i in itens if i.status == BatchItemStatus.FAILED],
        "na_fila": [i for i in itens if i.status == BatchItemStatus.QUEUED],
        "recusados": [i for i in itens if i.status == BatchItemStatus.SKIPPED],
    }


def indicadores() -> dict[str, Any]:
    todos = list(lotes())
    return {
        "total": len(todos),
        "em_execucao": sum(1 for l in todos if l.status == "running"),
        "com_falha": sum(1 for l in todos if l.failed_count > 0),
        "documentos_emitidos": sum(l.published_count for l in todos),
    }
