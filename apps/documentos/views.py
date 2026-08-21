from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.ativos.models import Machine
from apps.ativos.selectors import maquinas
from motores.documento import TemplateDesconhecido, implementados
from motores.documento import template as template_do_catalogo

from . import armazenamento
from .enums import DocumentStatus, RenderStatus
from .verificacao import comprovar
from .integridade import conferir
from .models import Document
from .renderizacao import html_do_documento, pdf_do_html
from .selectors import documentos, indicadores_de_emissao
from .services import (
    PermissaoDePublicacao,
    PublicacaoBloqueada,
    criar_documento,
    montar,
    publicar,
    sincronizar_bloqueios,
)


@login_required
def lista_documentos(request: HttpRequest) -> HttpResponse:
    return render(request, "ui/documentos/lista.html", {
        "documentos": documentos(status=request.GET.get("status") or None),
        "indicadores": indicadores_de_emissao(),
        "templates": implementados(),
        "maquinas": maquinas(),
        "status": request.GET.get("status", ""),
        "estados": DocumentStatus.choices,
    })


@login_required
@require_POST
def emitir(request: HttpRequest) -> HttpResponse:
    maquina = get_object_or_404(Machine, public_uuid=request.POST.get("maquina"))
    try:
        template_do_catalogo(request.POST.get("template", ""))
    except TemplateDesconhecido as erro:
        messages.error(request, str(erro))
        return redirect("documentos")
    documento = criar_documento(
        machine=maquina, template_code=request.POST["template"], actor=request.user
    )
    return redirect("documento", uuid=documento.public_uuid)


@login_required
def detalhe_documento(request: HttpRequest, uuid: str) -> HttpResponse:
    documento = _documento(uuid)
    contexto = montar(documento=documento)
    sincronizar_bloqueios(documento=documento, contexto=contexto)
    documento.refresh_from_db()
    return render(request, "ui/documentos/emissao.html", {
        "documento": documento,
        "template": documento.template,
        "ctx": contexto,
        "versoes": documento.versions.select_related("published_by"),
        "pode_publicar": contexto.pode_publicar,
    })


@login_required
def painel_bloqueios(request: HttpRequest, uuid: str) -> HttpResponse:
    """Recarrega o painel do verificador sem sair da tela (HTMX)."""
    documento = _documento(uuid)
    contexto = montar(documento=documento)
    sincronizar_bloqueios(documento=documento, contexto=contexto)
    return render(request, "ui/documentos/_bloqueios.html", {
        "documento": documento,
        "template": documento.template,
        "ctx": contexto,
        "pode_publicar": contexto.pode_publicar,
    })


@login_required
def previa(request: HttpRequest, uuid: str) -> HttpResponse:
    """Prévia em tela — o MESMO HTML que compõe o PDF."""
    documento = _documento(uuid)
    return HttpResponse(
        html_do_documento(
            documento=documento, contexto=montar(documento=documento), request=request
        )
    )


@login_required
@require_POST
def publicar_documento(request: HttpRequest, uuid: str) -> HttpResponse:
    documento = _documento(uuid)
    try:
        versao = publicar(documento=documento, actor=request.user)
    except PublicacaoBloqueada as bloqueio:
        messages.error(
            request,
            f"Publicação recusada: {len(bloqueio.violacoes)} bloqueio(s) do verificador.",
        )
        return redirect("documento", uuid=uuid)
    except PermissaoDePublicacao as erro:
        messages.error(request, str(erro))
        return redirect("documento", uuid=uuid)
    messages.success(request, f"{documento.template.nome} publicado na versão {versao.number}.")
    return HttpResponseRedirect(reverse("documento", args=[uuid]))


@login_required
def baixar_pdf(request: HttpRequest, uuid: str) -> HttpResponse:
    """Serve o PDF publicado.

    Ordem de preferência: URL assinada do bucket (a aplicação não trafega o binário),
    streaming do armazenamento e, por último, composição em linha — que é rede de
    segurança de ambiente sem worker, nunca o caminho normal.
    """
    documento = _documento(uuid)
    versao = documento.current_version
    if versao is None:
        messages.error(request, "Documento ainda não publicado — não há PDF para baixar.")
        return redirect("documento", uuid=uuid)
    nome = f"{documento.number.replace('/', '-')}-v{versao.number}.pdf"

    if versao.render_status == RenderStatus.RENDERED and armazenamento.existe(versao.pdf_key):
        assinada = armazenamento.url_temporaria(versao.pdf_key)
        if assinada:
            return HttpResponseRedirect(assinada)
        return FileResponse(
            armazenamento.abrir(versao.pdf_key), content_type="application/pdf", filename=nome
        )

    html = html_do_documento(documento=documento, contexto=montar(documento=documento))
    try:
        conteudo, _ = pdf_do_html(html, base_url=str(settings.BASE_DIR))
    except Exception as erro:  # noqa: BLE001 - libs de composição ausentes no ambiente
        messages.error(
            request,
            "O PDF ainda não foi composto e a composição em linha falhou neste ambiente "
            f"({type(erro).__name__}). Use a prévia de impressão para imprimir ou salvar.",
        )
        return redirect("documento", uuid=uuid)
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    return resposta


@login_required
def integridade_documento(request: HttpRequest, uuid: str) -> HttpResponse:
    """Recalcula o hash do binário guardado e compara com o registrado na publicação."""
    documento = _documento(uuid)
    versao = documento.current_version
    conferencia = conferir(versao) if versao is not None else None
    return render(
        request,
        "ui/documentos/_integridade.html",
        {
            "documento": documento, "versao": versao, "conferencia": conferencia,
            "em_bucket": armazenamento.em_bucket(),
        },
    )


def _documento(uuid: str) -> Document:
    return get_object_or_404(
        Document.objects.select_related("machine", "machine__client", "project", "current_version"),
        public_uuid=uuid,
    )


def verificacao_publica_html(request: HttpRequest, uuid: str) -> HttpResponse:
    """Destino do QR impresso. Sem login, sem sessão, sem conteúdo técnico (CA-06)."""
    versao = request.GET.get("v")
    comprovacao = comprovar(
        str(uuid), versao_numero=int(versao) if versao and versao.isdigit() else None
    )
    return render(
        request,
        "ui/publico/verificacao.html",
        {"c": comprovacao},
        status=200 if comprovacao.encontrado else 404,
    )
