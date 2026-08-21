from __future__ import annotations

from django.db import models

from .tenancy import get_clientes, get_tenant, require_tenant


class TenantQuerySet(models.QuerySet):
    def do_tenant_atual(self) -> TenantQuerySet:
        return self.filter(tenant_id=require_tenant())

    def da_carteira(self) -> TenantQuerySet:
        """Aplica a restrição de carteira do contexto, se houver."""
        return _filtrar_por_carteira(self, self.model)

    def de_todos_os_clientes(self) -> TenantQuerySet:
        """Ignora a carteira DELIBERADAMENTE — exige comentário justificando o uso."""
        return self


def _caminho_do_cliente(model: type[models.Model]) -> str | None:
    """Caminho de consulta até o cliente, declarado no próprio modelo.

    Cada tabela sabe como se liga ao cliente: `Machine` tem FK direta, `Hazard` chega
    por `machine__client`. Declarar em vez de adivinhar é o que permite adicionar uma
    tabela nova sem que ela escape do escopo por acidente — sem a declaração, o filtro
    NÃO é aplicado, e há um teste que lista as tabelas sem declaração.
    """
    return getattr(model, "caminho_para_cliente", None)


def _filtrar_por_carteira(qs: models.QuerySet, model: type[models.Model]) -> models.QuerySet:
    carteira = get_clientes()
    if carteira is None:  # sem restrição: administrador, fila, tarefa de sistema
        return qs
    caminho = _caminho_do_cliente(model)
    if caminho is None:
        return qs
    return qs.filter(**{f"{caminho}__in": carteira})


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """Manager padrão de toda tabela de negócio.

    Aplica DUAS camadas: o tenant do contexto (isolamento, obrigatório) e a carteira de
    clientes (visibilidade, opcional). Quando não há tenant no contexto, levanta — em vez
    de devolver silenciosamente os dados de todas as organizações.
    """

    def get_queryset(self) -> TenantQuerySet:
        qs = TenantQuerySet(self.model, using=self._db).filter(tenant_id=require_tenant())
        return _filtrar_por_carteira(qs, self.model)


class SemEscopoManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    """Acesso deliberadamente irrestrito — migração, tarefa de sistema, admin.

    Todo uso precisa de comentário justificando por que o escopo não se aplica.
    """


def tenant_do_contexto() -> int | None:
    return get_tenant()


def carteira_do_contexto() -> frozenset[int] | None:
    return get_clientes()
