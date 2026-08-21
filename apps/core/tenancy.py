"""Contexto de escopo da requisição: organização e carteira de clientes.

Duas camadas, e a distinção entre elas é a decisão central deste módulo:

**Tenant** é fronteira de ISOLAMENTO. Dado de outra organização não existe — vazamento
aqui é incidente de segurança. Consulta sem tenant no contexto levanta, em vez de
devolver silenciosamente os dados de todos.

**Carteira de clientes** é fronteira de VISIBILIDADE dentro da mesma organização. O
técnico da Life Laboral vê apenas os clientes atribuídos a ele; o administrador vê todos.
Ausência de restrição é representada por `None` — e `None` significa "vê tudo do tenant",
nunca "vê nada". Um conjunto VAZIO significa o oposto: nenhum cliente atribuído, portanto
nenhum dado. Confundir os dois é o erro fácil aqui, por isso são tipos distintos.

O contexto é propagado por contextvars para que a fila Celery possa herdá-lo sem depender
do objeto request.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_tenant_id: ContextVar[int | None] = ContextVar("tenant_id", default=None)
# None = sem restrição (vê todos os clientes do tenant). frozenset() = nenhum cliente.
_clientes: ContextVar[frozenset[int] | None] = ContextVar("clientes", default=None)


class TenantEscopoAusente(RuntimeError):
    """Levantada quando uma consulta com escopo é feita sem tenant no contexto."""


def set_tenant(tenant_id: int | None) -> None:
    _tenant_id.set(tenant_id)


def get_tenant() -> int | None:
    return _tenant_id.get()


def require_tenant() -> int:
    tenant_id = _tenant_id.get()
    if tenant_id is None:
        raise TenantEscopoAusente(
            "Consulta com escopo de tenant executada sem tenant no contexto."
        )
    return tenant_id


def set_clientes(client_ids: frozenset[int] | set[int] | list[int] | None) -> None:
    """Define a carteira. `None` libera todos os clientes do tenant."""
    _clientes.set(None if client_ids is None else frozenset(client_ids))


def get_clientes() -> frozenset[int] | None:
    return _clientes.get()


def sem_restricao_de_cliente() -> bool:
    return _clientes.get() is None


@contextmanager
def usando_tenant(tenant_id: int | None) -> Iterator[None]:
    """Escopo de organização SEM restrição de carteira — tarefa de sistema e fila.

    A fila trabalha em nome da organização, não de uma pessoa: uma tarefa que compõe o
    PDF de um documento não pode falhar porque o usuário que publicou tem carteira
    restrita.
    """
    token_tenant = _tenant_id.set(tenant_id)
    token_clientes = _clientes.set(None)
    try:
        yield
    finally:
        _clientes.reset(token_clientes)
        _tenant_id.reset(token_tenant)


@contextmanager
def usando_escopo(
    tenant_id: int | None, client_ids: frozenset[int] | set[int] | list[int] | None
) -> Iterator[None]:
    """Escopo completo — organização e carteira. Usado pelo middleware e nos testes."""
    token_tenant = _tenant_id.set(tenant_id)
    token_clientes = _clientes.set(None if client_ids is None else frozenset(client_ids))
    try:
        yield
    finally:
        _clientes.reset(token_clientes)
        _tenant_id.reset(token_tenant)
