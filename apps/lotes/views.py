from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.clientes.models import Client
from apps.documentos.services import PermissaoDePublicacao
from motores.documento import CATALOGO
from motores.lote import LIMITE_POR_LOTE, motivo_de_recusa

from .models import IssueBatch
from .selectors import detalhe, indicadores, lotes
from .services import LoteVazio, abrir_lote, cancelar_lote, executar_lote, planejar_lote


@login_required
def lista_lotes(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "ui/lotes/lista.html",
        {
            "lotes": lotes()[:40],
            "indicadores": indicadores(),
            "templates": [t for t in CATALOGO.values() if t.implementado],
            "clientes": Client.objects.order_by("legal_name")[:100],
            "limite": LIMITE_POR_LOTE,
        },
    )


@login_required
@require_POST
def planejar(request: HttpRequest) -> HttpResponse:
    """Mostra o plano ANTES de enfileirar. É o passo que evita a espera inútil."""
    codigo = request.POST.get("template_code") or ""
    cliente = (
        Client.objects.filter(public_uuid=request.POST.get("client")).first()
        if request.POST.get("client")
        else None
    )
    plano = planejar_lote(template_code=codigo, client=cliente, actor=request.user)
    return render(
        request,
        "ui/lotes/_plano.html",
        {
            "plano": plano,
            "template_code": codigo,
            "cliente": cliente,
            "recusas": [motivo_de_recusa(i) for i in plano.recusadas],
            "limite": LIMITE_POR_LOTE,
        },
    )


@login_required
@require_POST
def confirmar(request: HttpRequest) -> HttpResponse:
    codigo = request.POST.get("template_code") or ""
    cliente = (
        Client.objects.filter(public_uuid=request.POST.get("client")).first()
        if request.POST.get("client")
        else None
    )
    plano = planejar_lote(template_code=codigo, client=cliente, actor=request.user)
    try:
        lote = abrir_lote(
            template_code=codigo, plano=plano, actor=request.user, client=cliente
        )
    except (LoteVazio, PermissaoDePublicacao) as erro:
        messages.error(request, str(erro))
        return redirect("lotes")

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        executar_lote(batch_id=lote.pk, actor_id=request.user.pk)
    else:
        from .tasks import executar_lote_task

        executar_lote_task.delay(lote.pk, request.user.pk)
    messages.success(
        request,
        f"Lote {lote.number} enfileirado com {lote.requested_count} documento(s). "
        "Você pode fechar esta tela — o resultado fica registrado.",
    )
    return redirect("lote", uuid=lote.public_uuid)


@login_required
def detalhe_lote(request: HttpRequest, uuid: str) -> HttpResponse:
    lote = get_object_or_404(IssueBatch.objects.select_related("client"), public_uuid=uuid)
    contexto = detalhe(lote)
    template = "ui/lotes/_progresso.html" if request.htmx else "ui/lotes/lote.html"
    return render(request, template, contexto)


@login_required
@require_POST
def cancelar(request: HttpRequest, uuid: str) -> HttpResponse:
    lote = get_object_or_404(IssueBatch, public_uuid=uuid)
    cancelar_lote(batch=lote, actor=request.user)
    messages.success(
        request,
        f"Lote {lote.number} cancelado. Os {lote.published_count} documento(s) já publicados "
        "permanecem — versão publicada é imutável.",
    )
    return redirect("lote", uuid=uuid)
