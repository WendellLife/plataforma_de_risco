from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .tenancy import set_clientes, set_tenant


class TenantMiddleware:
    """Publica no contexto da execução as duas camadas de escopo do usuário.

    Organização (isolamento) e carteira de clientes (visibilidade). A carteira é resolvida
    UMA vez por requisição, aqui — não a cada consulta — e fica no contextvar de onde
    managers e filas a leem.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        autenticado = bool(user and user.is_authenticated)
        tenant_id = getattr(user, "tenant_id", None) if autenticado else None

        set_tenant(tenant_id)
        # Anônimo entra sem restrição de carteira porque também entra sem tenant: sem
        # tenant, nenhuma consulta com escopo passa. A superfície pública (verificação do
        # QR) usa managers sem escopo, de propósito e documentadamente.
        carteira = user.carteira() if autenticado and tenant_id else None
        set_clientes(carteira)

        request.tenant_id = tenant_id  # type: ignore[attr-defined]
        request.carteira = carteira  # type: ignore[attr-defined]
        try:
            return self.get_response(request)
        finally:
            set_clientes(None)
            set_tenant(None)
