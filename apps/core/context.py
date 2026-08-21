from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def shell(request: HttpRequest) -> dict[str, Any]:
    """Dados do esqueleto (barra lateral e cabeçalho) disponíveis em toda tela.

    O escopo de visibilidade aparece aqui de propósito: quem vê o quê precisa ser óbvio
    na barra lateral, não descoberto depois de estranhar uma lista curta. E um usuário sem
    carteira precisa entender que as telas estão vazias por falta de acesso, não por falta
    de dado.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"shell": None}

    carteira = getattr(request, "carteira", None)
    toda_a_organizacao = carteira is None
    sem_carteira = carteira is not None and len(carteira) == 0

    if toda_a_organizacao:
        escopo = "Toda a organização"
    elif sem_carteira:
        escopo = "Sem clientes atribuídos"
    else:
        escopo = f"{len(carteira)} cliente(s)"

    return {
        "shell": {
            "usuario": user,
            "tenant": getattr(user, "tenant", None),
            "perfil": user.get_role_display(),
            "pode_publicar": user.pode_publicar,
            "administra": user.ve_toda_a_organizacao,
            "somente_leitura": user.somente_leitura,
            "escopo": escopo,
            "sem_carteira": sem_carteira,
        }
    }
