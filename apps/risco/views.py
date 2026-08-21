from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.ativos.models import Machine
from motores.hrn import METHOD_VERSION, TOLERAVEIS, comparar, escala_visual, estimar

from .enums import EstimateKind
from .forms import FatoresForm
from .models import Hazard
from .selectors import apreciacao_da_maquina, linha_de_perigo, _resultado
from .services import registrar_estimativa


def _hazard(uuid: str) -> Hazard:
    return get_object_or_404(
        Hazard.objects.select_related("machine", "machine__client"), public_uuid=uuid
    )


def _rotulo_tipo(kind: str) -> str:
    return dict(EstimateKind.choices).get(kind, kind)


@login_required
def apreciacao(request: HttpRequest, uuid: str) -> HttpResponse:
    maquina = get_object_or_404(
        Machine.objects.select_related("client", "org_unit", "machine_type"), public_uuid=uuid
    )
    return render(
        request,
        "ui/risco/apreciacao.html",
        {"maquina": maquina, "apreciacao": apreciacao_da_maquina(maquina),
         "method_version": METHOD_VERSION},
    )


def _contexto_calculadora(hazard: Hazard, kind: str, form: FatoresForm) -> dict[str, Any]:
    return {
        "hazard": hazard,
        "kind": kind,
        "rotulo_tipo": _rotulo_tipo(kind),
        "form": form,
        "fatores": form.fatores_meta,
        "linha": linha_de_perigo(hazard),
        "method_version": METHOD_VERSION,
    }


@login_required
def calculadora(request: HttpRequest, uuid: str, kind: str) -> HttpResponse:
    """Abre a calculadora já preenchida com a estimativa gravada, se houver."""
    hazard = _hazard(uuid)
    gravada = hazard.estimates.filter(kind=kind).first()
    inicial = (
        {"lo": format(gravada.lo.normalize(), "f"), "fe": format(gravada.fe.normalize(), "f"),
         "dph": format(gravada.dph.normalize(), "f"), "np": format(gravada.np.normalize(), "f")}
        if gravada
        else None
    )
    return render(
        request,
        "ui/risco/_calculadora.html",
        _contexto_calculadora(hazard, kind, FatoresForm(initial=inicial)),
    )


def _previa(hazard: Hazard, kind: str, form: FatoresForm) -> dict[str, Any]:
    """Cálculo ao vivo. Roda no servidor, NÃO grava — a gravação é ato explícito."""
    ctx: dict[str, Any] = {
        "hazard": hazard, "kind": kind, "rotulo_tipo": _rotulo_tipo(kind),
        "form": form, "method_version": METHOD_VERSION, "salvo": False,
        "toleraveis": [str(b) for b in TOLERAVEIS],
    }
    if not form.is_valid():
        ctx["erro"] = "Escolha um descritor para os quatro fatores."
        return ctx
    resultado = estimar(form.fatores())
    ctx["resultado"] = resultado
    ctx["escala"] = escala_visual(resultado.produto)

    # Contraparte gravada: mostra o movimento antes de gravar.
    outro = EstimateKind.INITIAL if kind == EstimateKind.RESIDUAL else EstimateKind.RESIDUAL
    contraparte = hazard.estimates.filter(kind=outro).first()
    if contraparte is not None:
        par = (
            (_resultado(contraparte), resultado)
            if kind == EstimateKind.RESIDUAL
            else (resultado, _resultado(contraparte))
        )
        try:
            ctx["comparacao"] = comparar(*par)
        except ValueError as exc:
            ctx["aviso_metodo"] = str(exc)
    elif kind == EstimateKind.INITIAL and hazard.recommendations.exists():
        ctx["pendencia_d03"] = True
    return ctx


@require_POST
@login_required
def previa_hrn(request: HttpRequest, uuid: str, kind: str) -> HttpResponse:
    hazard = _hazard(uuid)
    ctx = _previa(hazard, kind, FatoresForm(request.POST))
    return render(request, "ui/risco/_resultado.html", ctx)


@require_POST
@login_required
def salvar_hrn(request: HttpRequest, uuid: str, kind: str) -> HttpResponse:
    hazard = _hazard(uuid)
    form = FatoresForm(request.POST)
    if not form.is_valid():
        return render(
            request, "ui/risco/_resultado.html", _previa(hazard, kind, form), status=422
        )
    f = form.fatores()
    registrar_estimativa(
        hazard=hazard, kind=kind, lo=f.lo, fe=f.fe, dph=f.dph, np=f.np,
        actor=request.user if request.user.is_authenticated else None,
    )
    hazard.refresh_from_db()
    ctx = _previa(_hazard(uuid), kind, FatoresForm(request.POST))
    ctx["salvo"] = True
    return render(request, "ui/risco/_resultado.html", ctx)
