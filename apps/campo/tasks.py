"""Fila "sincronizacao" — trabalho pesado que não pode atrasar a resposta ao aparelho."""

from __future__ import annotations

from celery import shared_task

from apps.core.tenancy import usando_tenant


@shared_task(queue="sincronizacao")
def notificar_conflitos(batch_id: int) -> int:
    """Avisa que um lote precisa de revisão humana (evento sync.conflict, Espec 08)."""
    from .models import SyncBatch

    lote = SyncBatch.sem_escopo.select_related("device__operator").get(pk=batch_id)
    with usando_tenant(lote.tenant_id):
        return lote.conflict_count


@shared_task(queue="midia")
def preparar_derivadas(photo_id: int) -> int:
    """Registra o tamanho do binário da foto.

    Compressão, derivadas e marca d'água ainda NÃO acontecem aqui — o aparelho já envia
    a foto comprimida, e gerar derivadas exigiria uma biblioteca de imagem no worker.
    Por ora esta tarefa apenas confere que o binário chegou e grava o tamanho, para que
    a foto sem arquivo apareça como incidente em vez de passar em silêncio.
    """
    from apps.documentos import armazenamento

    from .models import FieldPhoto

    foto = FieldPhoto.sem_escopo.get(pk=photo_id)
    with usando_tenant(foto.tenant_id):
        if not armazenamento.existe(foto.file_key):
            return 0
        tamanho = len(armazenamento.ler(foto.file_key))
        foto.bytes_size = tamanho
        foto.save(update_fields=["bytes_size", "updated_at"])
        return tamanho
