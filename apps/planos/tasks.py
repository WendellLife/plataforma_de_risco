"""Fila "planos" — vencimento e escalonamento."""

from __future__ import annotations

from celery import shared_task

from apps.core.tenancy import usando_tenant


@shared_task(queue="planos")
def escalar_vencidas(tenant_id: int) -> int:
    """Escala ao gestor da licença as ações vencidas.

    Não grava estado "atrasada" em coluna: a situação é derivada a cada leitura. Esta
    tarefa apenas NOTIFICA — se ela falhar, o painel continua correto.
    """
    from .selectors import indicadores

    with usando_tenant(tenant_id):
        return indicadores()["vencidas"]
