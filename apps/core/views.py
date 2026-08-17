from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from apps.ativos.selectors import indicadores_do_parque, publicacoes_bloqueadas


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@login_required
def painel(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "ui/painel/index.html",
        {
            "indicadores": indicadores_do_parque(),
            "bloqueios": publicacoes_bloqueadas(),
        },
    )
