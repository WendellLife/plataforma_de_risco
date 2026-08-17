from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .tenancy import set_tenant


class TenantMiddleware:
    """Resolve o tenant do usuário autenticado e o publica no contexto da execução."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        tenant_id = getattr(user, "tenant_id", None) if user and user.is_authenticated else None
        set_tenant(tenant_id)
        request.tenant_id = tenant_id  # type: ignore[attr-defined]
        try:
            return self.get_response(request)
        finally:
            set_tenant(None)
