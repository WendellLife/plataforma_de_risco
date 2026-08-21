"""Consultas de leitura da apreciação de risco. Sempre com escopo de tenant."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Prefetch, QuerySet

from apps.ativos.models import Machine
from motores.hrn import Comparacao, Resultado, comparar, descritor

from .enums import EstimateKind
from .models import Hazard, HrnEstimate


def perigos_da_maquina(machine: Machine) -> QuerySet[Hazard]:
    return (
        Hazard.objects.filter(machine=machine)
        .select_related("safety_category")
        .prefetch_related(
            Prefetch("estimates", queryset=HrnEstimate.objects.all()),
            "recommendations",
            "recommendations__standard_reference",
        )
        .order_by("zone", "title")
    )


def _resultado(e: HrnEstimate) -> Resultado:
    from motores.hrn import ROTULOS, Band

    band = Band(e.band)
    return Resultado(
        produto=e.product, band=band, rotulo=ROTULOS[band], method_version=e.method_version
    )


def _fatores_legiveis(e: HrnEstimate) -> list[dict[str, str]]:
    return [
        {"sigla": sigla.upper(), "valor": format(valor.normalize(), "f"),
         "descritor": descritor(sigla, valor)}
        for sigla, valor in (("lo", e.lo), ("fe", e.fe), ("dph", e.dph), ("np", e.np))
    ]


def linha_de_perigo(hazard: Hazard) -> dict[str, Any]:
    """Uma zona de perigo com inicial, residual e o movimento entre as duas."""
    por_tipo = {e.kind: e for e in hazard.estimates.all()}
    inicial = por_tipo.get(EstimateKind.INITIAL)
    residual = por_tipo.get(EstimateKind.RESIDUAL)
    comparacao: Comparacao | None = None
    if inicial and residual:
        try:
            comparacao = comparar(_resultado(inicial), _resultado(residual))
        except ValueError:
            comparacao = None  # versões de método diferentes: mostra as duas, sem delta
    medidas = list(hazard.recommendations.all())
    return {
        "hazard": hazard,
        "inicial": inicial,
        "residual": residual,
        "fatores_inicial": _fatores_legiveis(inicial) if inicial else [],
        "fatores_residual": _fatores_legiveis(residual) if residual else [],
        "comparacao": comparacao,
        "medidas": medidas,
        "pendencia_d03": bool(medidas) and residual is None,
        "sem_estimativa": inicial is None,
        "metodo_divergente": bool(inicial and residual and comparacao is None),
    }


def apreciacao_da_maquina(machine: Machine) -> dict[str, Any]:
    linhas = [linha_de_perigo(h) for h in perigos_da_maquina(machine)]
    intoleraveis_antes = sum(
        1 for l in linhas if l["inicial"] and _resultado(l["inicial"]).band not in _toleraveis()
    )
    intoleraveis_depois = sum(
        1 for l in linhas if l["residual"] and _resultado(l["residual"]).band not in _toleraveis()
    )
    return {
        "linhas": linhas,
        "total": len(linhas),
        "sem_estimativa": sum(1 for l in linhas if l["sem_estimativa"]),
        "pendencias_d03": sum(1 for l in linhas if l["pendencia_d03"]),
        "intoleraveis_antes": intoleraveis_antes,
        "intoleraveis_depois": intoleraveis_depois,
        "reducao_media": _reducao_media(linhas),
    }


def _toleraveis():  # noqa: ANN202
    from motores.hrn import TOLERAVEIS

    return TOLERAVEIS


def _reducao_media(linhas: list[dict[str, Any]]) -> Decimal | None:
    valores = [l["comparacao"].reducao_percentual for l in linhas if l["comparacao"]]
    if not valores:
        return None
    return (sum(valores) / len(valores)).quantize(Decimal("0.1"))
