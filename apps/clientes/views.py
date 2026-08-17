from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .selectors import clientes


@login_required
def lista_clientes(request: HttpRequest) -> HttpResponse:
    return render(request, "ui/clientes/lista.html", {"clientes": clientes()})
