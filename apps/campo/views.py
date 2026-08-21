from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import SyncBatch
from .selectors import aparelhos, indicadores_de_campo, lotes


@login_required
def lista_lotes(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status") or None
    contexto = {
        "lotes": lotes(status=status)[:80],
        "aparelhos": aparelhos()[:20],
        "indicadores": indicadores_de_campo(),
        "status": status,
    }
    template = "ui/campo/_tabela.html" if request.htmx else "ui/campo/lotes.html"
    return render(request, template, contexto)


@login_required
def detalhe_lote(request: HttpRequest, uuid: str) -> HttpResponse:
    lote = get_object_or_404(
        SyncBatch.objects.select_related("device", "device__operator"), public_uuid=uuid
    )
    return render(
        request,
        "ui/campo/lote.html",
        {
            "lote": lote,
            "registros": lote.records.all().order_by("record_type", "status"),
            "conflitos": (lote.response or {}).get("conflict_report", []),
            "falhas": (lote.response or {}).get("failures", []),
            "avisos": (lote.response or {}).get("warnings", []),
        },
    )
