from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ativos.models import Machine
from apps.clientes.models import Client, Person

from .models import Action
from .selectors import (
    acoes,
    adequacao,
    curva_de_adequacao,
    indicadores,
    linha_de_acao,
    por_responsavel,
)
from .services import (
    AcaoJaEncerrada,
    EncerramentoSemEvidencia,
    PrazoSemJustificativa,
    anexar_evidencia,
    cancelar_acao,
    concluir_acao,
    gerar_acoes_de_nao_conformidade,
    iniciar_acao,
    repactuar_prazo,
)


def _acao(uuid: str) -> Action:
    return get_object_or_404(
        Action.objects.select_related("plan", "plan__machine", "owner"), public_uuid=uuid
    )


@login_required
def plano_da_maquina(request: HttpRequest, uuid: str) -> HttpResponse:
    maquina = get_object_or_404(
        Machine.objects.select_related("client", "project", "project__engineer"), public_uuid=uuid
    )
    lista = [linha_de_acao(a) for a in acoes(machine=maquina)]
    return render(
        request,
        "ui/planos/plano.html",
        {
            "maquina": maquina,
            "linhas": lista,
            "adequacao": adequacao(machine=maquina),
            "indicadores": indicadores(client=maquina.client),
            # Person não tem vínculo com cliente: pessoa do tenant atende vários clientes.
            "responsaveis": Person.objects.order_by("name")[:50],
        },
    )


@login_required
def lista_de_acoes(request: HttpRequest) -> HttpResponse:
    """Visão do gestor: ações de todas as máquinas, vencidas primeiro."""
    situacao = request.GET.get("situacao") or None
    linhas = [linha_de_acao(a) for a in acoes()]
    if situacao:
        linhas = [l for l in linhas if l["situacao"] == situacao]
    ordem = {"vencida": 0, "a_vencer": 1, "em_execucao": 2, "aberta": 3,
             "concluida": 4, "cancelada": 5}
    linhas.sort(key=lambda l: (ordem.get(l["situacao"], 9), l["acao"].deadline))
    return render(
        request,
        "ui/planos/acoes.html",
        {"linhas": linhas, "indicadores": indicadores(), "situacao": situacao},
    )


@login_required
def painel_de_adequacao(request: HttpRequest, uuid: str) -> HttpResponse:
    cliente = get_object_or_404(Client, public_uuid=uuid)
    return render(
        request,
        "ui/planos/adequacao.html",
        {
            "cliente": cliente,
            "indicadores": indicadores(client=cliente),
            "curva": curva_de_adequacao(client=cliente),
            "responsaveis": por_responsavel(client=cliente),
        },
    )


@login_required
@require_POST
def gerar_acoes(request: HttpRequest, uuid: str) -> HttpResponse:
    maquina = get_object_or_404(Machine, public_uuid=uuid)
    try:
        criadas = gerar_acoes_de_nao_conformidade(machine=maquina, actor=request.user)
    except ValueError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{len(criadas)} ação(ões) gerada(s) a partir dos achados."
            if criadas
            else "Nenhum achado sem ação — o plano já está completo.",
        )
    return redirect("plano_maquina", uuid=uuid)


@login_required
@require_POST
def iniciar(request: HttpRequest, uuid: str) -> HttpResponse:
    acao = _acao(uuid)
    try:
        iniciar_acao(action=acao, actor=request.user)
    except AcaoJaEncerrada as erro:
        messages.error(request, str(erro))
    return redirect("plano_maquina", uuid=acao.plan.machine.public_uuid)


@login_required
@require_POST
def concluir(request: HttpRequest, uuid: str) -> HttpResponse:
    acao = _acao(uuid)
    try:
        concluir_acao(action=acao, actor=request.user)
    except (EncerramentoSemEvidencia, AcaoJaEncerrada) as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Ação {acao.code} encerrada com evidência.")
    return redirect("plano_maquina", uuid=acao.plan.machine.public_uuid)


@login_required
@require_POST
def evidenciar(request: HttpRequest, uuid: str) -> HttpResponse:
    acao = _acao(uuid)
    chave = (request.POST.get("file_key") or "").strip()
    if not chave:
        messages.error(request, "Informe a chave do arquivo de evidência.")
    else:
        anexar_evidencia(
            action=acao, file_key=chave, kind=request.POST.get("kind") or "photo",
            caption=request.POST.get("caption") or "", actor=request.user,
        )
    return redirect("plano_maquina", uuid=acao.plan.machine.public_uuid)


@login_required
@require_POST
def repactuar(request: HttpRequest, uuid: str) -> HttpResponse:
    acao = _acao(uuid)
    try:
        repactuar_prazo(
            action=acao, novo_prazo=request.POST["novo_prazo"],
            reason=request.POST.get("justificativa") or "", actor=request.user,
        )
    except (PrazoSemJustificativa, AcaoJaEncerrada, KeyError) as erro:
        messages.error(request, str(erro) or "Informe o novo prazo.")
    return redirect("plano_maquina", uuid=acao.plan.machine.public_uuid)


@login_required
@require_POST
def cancelar(request: HttpRequest, uuid: str) -> HttpResponse:
    acao = _acao(uuid)
    try:
        cancelar_acao(action=acao, reason=request.POST.get("motivo") or "", actor=request.user)
    except (ValueError, AcaoJaEncerrada) as erro:
        messages.error(request, str(erro))
    return redirect("plano_maquina", uuid=acao.plan.machine.public_uuid)
