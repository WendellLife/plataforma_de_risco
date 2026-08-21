"""Autenticação por token de aparelho.

Credencial separada da sessão web e com alcance menor: só rotas de coleta e
sincronização (Espec 08, item 8). O token nunca é gravado em claro — o banco guarda
o SHA-256 — e o tenant é derivado da credencial, jamais aceito como parâmetro.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.core.tenancy import set_clientes, set_tenant

from .enums import DeviceStatus
from .services import aparelho_por_token

PREFIXO = "Device "


class DeviceTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):  # noqa: ANN001, ANN201
        cabecalho = request.headers.get("Authorization", "")
        if not cabecalho.startswith(PREFIXO):
            return None
        token = cabecalho[len(PREFIXO):].strip()
        if not token:
            raise exceptions.AuthenticationFailed("Token de aparelho ausente.")

        aparelho = aparelho_por_token(token)
        if aparelho is None:
            raise exceptions.AuthenticationFailed("Aparelho não pareado ou token revogado.")
        if aparelho.expires_at <= timezone.now():
            aparelho.status = DeviceStatus.EXPIRED
            aparelho.save(update_fields=["status", "updated_at"])
            raise exceptions.AuthenticationFailed(
                "Token do aparelho expirou. Refaça o pareamento para continuar coletando."
            )

        set_tenant(aparelho.tenant_id)
        # A carteira do operador vale na API igual à web: o aparelho não é uma porta
        # lateral. Sem isto, um técnico com telefone pareado leria o parque inteiro.
        set_clientes(aparelho.operator.carteira())
        request.device = aparelho
        return (aparelho.operator, aparelho)

    def authenticate_header(self, request):  # noqa: ANN001, ANN201
        return "Device"
