"""Verificador de coerência — esqueleto.

Executa antes de toda publicação (Espec 01, item 7). Cada regra tem o identificador
do defeito observado no acervo legado, e cada regra tem um teste em
tests/defeitos/ com esse identificador no nome.

As regras de conteúdo entram no Sprint 6; aqui está o contrato e as duas primeiras.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severidade(StrEnum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: str
    severidade: Severidade
    mensagem: str
    entidade: dict[str, Any] = field(default_factory=dict)
    caminho_correcao: str = ""


Regra = Callable[[dict[str, Any]], list[Violacao]]
_REGRAS: dict[str, Regra] = {}


def regra(codigo: str) -> Callable[[Regra], Regra]:
    def _registrar(fn: Regra) -> Regra:
        _REGRAS[codigo] = fn
        return fn

    return _registrar


@regra("D-01")
def fonte_sem_ponto_de_bloqueio(ctx: dict[str, Any]) -> list[Violacao]:
    """Fonte de energia cadastrada sem ponto de bloqueio bloqueia LOTO e laudo."""
    return [
        Violacao(
            regra="D-01",
            severidade=Severidade.BLOCK,
            mensagem=(
                f"Fonte {fonte['rotulo']} sem ponto de bloqueio — "
                "o procedimento LOTO não pode ser emitido."
            ),
            entidade={"type": "energy_source", "uuid": fonte["uuid"], "label": fonte["rotulo"]},
            caminho_correcao=f"/maquinas/{ctx['machine_uuid']}/energia",
        )
        for fonte in ctx.get("fontes_sem_bloqueio", [])
    ]


@regra("D-03")
def risco_sem_residual(ctx: dict[str, Any]) -> list[Violacao]:
    """Medida de proteção proposta exige reestimativa de HRN."""
    return [
        Violacao(
            regra="D-03",
            severidade=Severidade.BLOCK,
            mensagem=f"Risco “{risco['rotulo']}” tem medida proposta sem HRN residual recalculado.",
            entidade={"type": "hazard", "uuid": risco["uuid"], "label": risco["rotulo"]},
            caminho_correcao=f"/hazards/{risco['uuid']}/estimativas",
        )
        for risco in ctx.get("riscos_sem_residual", [])
    ]


def verificar(contexto: dict[str, Any]) -> list[Violacao]:
    """Roda todas as regras registradas e devolve TODAS as violações de uma vez."""
    violacoes: list[Violacao] = []
    for fn in _REGRAS.values():
        violacoes.extend(fn(contexto))
    return violacoes
