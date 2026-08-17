from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def shell(request: HttpRequest) -> dict[str, Any]:
    """Dados do esqueleto (barra lateral e cabeçalho) disponíveis em toda tela."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"shell": None}
    return {
        "shell": {
            "usuario": user,
            "tenant": getattr(user, "tenant", None),
            "perfil": user.get_role_display(),
            "pode_publicar": user.pode_publicar,
        }
    }
