"""Fila "midia" — compressão, derivadas e marca d'água. Sprint 11."""

from celery import shared_task


@shared_task(queue="midia")
def processar_foto(photo_id: int) -> None:
    raise NotImplementedError("Sprint 11 — evidência fotográfica.")
