from __future__ import annotations

from django.db import models

from .tenancy import get_tenant, require_tenant


class TenantQuerySet(models.QuerySet):
    def do_tenant_atual(self) -> TenantQuerySet:
        return self.filter(tenant_id=require_tenant())


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """Manager padrão de toda tabela de negócio.

    get_queryset() aplica o escopo do tenant do contexto automaticamente. Quando não
    há tenant no contexto, levanta — em vez de devolver silenciosamente os dados de
    todos os clientes.
    """

    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db).filter(tenant_id=require_tenant())


class SemEscopoManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """Acesso deliberadamente irrestrito — migração, tarefa de sistema, admin.

    Todo uso precisa de comentário justificando por que o escopo não se aplica.
    """


def tenant_do_contexto() -> int | None:
    return get_tenant()
