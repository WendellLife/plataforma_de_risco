from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.clientes.selectors import clientes

from .models import Machine
from .selectors import maquinas


@login_required
def lista_maquinas(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status") or None
    contexto = {
        "maquinas": maquinas(busca=busca, status=status),
        "clientes": clientes(),
        "busca": busca,
        "status": status,
    }
    # Requisição HTMX devolve apenas a tabela, não a tela inteira
    template = "ui/maquinas/_tabela.html" if request.htmx else "ui/maquinas/lista.html"
    return render(request, template, contexto)


@login_required
def ficha_maquina(request: HttpRequest, uuid: str) -> HttpResponse:
    maquina = get_object_or_404(
        Machine.objects.select_related("client", "org_unit", "machine_type"), public_uuid=uuid
    )
    return render(
        request,
        "ui/maquinas/ficha.html",
        {
            "maquina": maquina,
            "fontes": maquina.energy_sources.select_related("lockout_point"),
            "componentes": maquina.components.all(),
        },
    )
