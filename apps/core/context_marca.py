"""Marca aplicada à interface.

Regra: a interface leva a marca do cliente APENAS quando não há ambiguidade sobre de quem
é o dado na tela — ou seja, quando o usuário vê exatamente um cliente. Um técnico com
cinco clientes na carteira vendo a cor de um deles seria enganoso.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from motores.marca import Superficie, resolver, variaveis_css

PLATAFORMA = "Life Laboral"


def marca(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"marca": resolver(superficie=Superficie.INTERFACE, plataforma=PLATAFORMA)}

    carteira = getattr(request, "carteira", None)
    dados = None
    # Um único cliente na carteira: a tela é inequivocamente dele.
    if carteira is not None and len(carteira) == 1:
        from apps.clientes.models import Client

        cliente = Client.sem_escopo.filter(pk=next(iter(carteira))).first()
        if cliente is not None and cliente.tem_marca_propria:
            dados = cliente.marca_dict

    identidade = resolver(
        superficie=Superficie.INTERFACE, plataforma=PLATAFORMA, cliente=dados
    )
    return {"marca": identidade, "marca_css": variaveis_css(identidade)}
