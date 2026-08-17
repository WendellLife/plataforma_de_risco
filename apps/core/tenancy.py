"""Contexto de tenant da requisição.

Regra AD-10 / CLAUDE.md nº 9: consulta sem escopo de tenant é bug de segurança.
O contexto é propagado por contextvars, de forma que a fila Celery possa herdá-lo
sem depender do objeto request.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

_tenant_id: ContextVar[int | None] = ContextVar("tenant_id", default=None)


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


@contextmanager
def usando_tenant(tenant_id: int | None) -> Iterator[None]:
    token = _tenant_id.set(tenant_id)
    try:
        yield
    finally:
        _tenant_id.reset(token)
