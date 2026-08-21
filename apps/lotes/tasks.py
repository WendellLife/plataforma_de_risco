"""Fila "lotes" — emissão em massa.

Fila SEPARADA de "documentos" de propósito: um lote de 100 documentos não pode empurrar
para o fim da fila a composição de PDF de quem acabou de publicar uma peça individual.
"""

from __future__ import annotations

from celery import shared_task

from apps.core.tenancy import usando_tenant


@shared_task(queue="lotes", bind=True, max_retries=1)
def executar_lote_task(self, batch_id: int, actor_id: int) -> dict[str, int]:  # noqa: ANN001
    from .models import IssueBatch
    from .services import executar_lote

    tenant_id = IssueBatch.sem_escopo.values_list("tenant_id", flat=True).get(pk=batch_id)
    with usando_tenant(tenant_id):
        lote = executar_lote(batch_id=batch_id, actor_id=actor_id)
        return {
            "publicados": lote.published_count,
            "falhos": lote.failed_count,
            "minutos": lote.duracao_minutos or 0,
        }
