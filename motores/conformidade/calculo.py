"""Motor de conformidade de checklist.

Duas regras que este motor existe para garantir (Espec 01, item 6):

1. O percentual é publicado em DOIS denominadores — base fixa da biblioteca e itens
   efetivamente avaliados. Publicar apenas um permite que máquinas com bases
   diferentes pareçam equivalentes.
2. Item marcado como não aplicável não desaparece: entra na contagem de avaliados
   apenas como exclusão explícita e sempre exige justificativa (defeito D-18).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ResultadoItem(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class Resposta:
    library_key: str
    resultado: ResultadoItem
    justificativa: str = ""

    def __post_init__(self) -> None:
        if self.resultado is ResultadoItem.NOT_APPLICABLE and not self.justificativa.strip():
            raise ValueError(
                f"{self.library_key}: item não aplicável exige justificativa (D-18)"
            )


@dataclass(frozen=True, slots=True)
class Conformidade:
    base_fixa: int
    avaliados: int
    conformes: Decimal
    nao_conformes: int
    nao_aplicaveis: int
    percentual_base_fixa: Decimal
    percentual_avaliados: Decimal


# Item parcial conta como meia conformidade — decisão de produto, não de norma.
PESO = {
    ResultadoItem.COMPLIANT: Decimal("1"),
    ResultadoItem.PARTIAL: Decimal("0.5"),
    ResultadoItem.NON_COMPLIANT: Decimal("0"),
}


def _pct(numerador: Decimal, denominador: int) -> Decimal:
    if denominador <= 0:
        return Decimal("0.0")
    return (numerador / Decimal(denominador) * 100).quantize(Decimal("0.1"))


def calcular(respostas: list[Resposta], base_fixa: int) -> Conformidade:
    aplicaveis = [r for r in respostas if r.resultado is not ResultadoItem.NOT_APPLICABLE]
    conformes = sum((PESO[r.resultado] for r in aplicaveis), Decimal("0"))
    return Conformidade(
        base_fixa=base_fixa,
        avaliados=len(aplicaveis),
        conformes=conformes,
        nao_conformes=sum(1 for r in aplicaveis if r.resultado is ResultadoItem.NON_COMPLIANT),
        nao_aplicaveis=len(respostas) - len(aplicaveis),
        percentual_base_fixa=_pct(conformes, base_fixa),
        percentual_avaliados=_pct(conformes, len(aplicaveis)),
    )
