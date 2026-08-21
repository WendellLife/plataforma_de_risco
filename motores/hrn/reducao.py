"""Comparação entre estimativa inicial e residual.

O produto isolado não decide nada. O que a apreciação precisa mostrar — e o que o
documento imprime — é o movimento: de qual faixa para qual faixa, em quantos degraus,
com qual redução percentual. Sem residual não existe comparação, e é exatamente essa
ausência que a regra D-03 do verificador bloqueia.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .calculo import Band, Resultado
from .escalas import indice_da_faixa

# Faixas em que o risco residual é aceitável sem decisão registrada.
TOLERAVEIS: frozenset[Band] = frozenset({Band.NEGLIGIBLE, Band.VERY_LOW, Band.LOW})


@dataclass(frozen=True, slots=True)
class Comparacao:
    inicial: Resultado
    residual: Resultado
    degraus: int
    reducao_percentual: Decimal
    residual_tolerabel: bool
    piorou: bool

    @property
    def melhorou(self) -> bool:
        return self.degraus > 0

    @property
    def exige_decisao(self) -> bool:
        """Residual fora de faixa tolerável só passa com decisão registrada (AD-07)."""
        return not self.residual_tolerabel


def comparar(inicial: Resultado, residual: Resultado) -> Comparacao:
    if inicial.method_version != residual.method_version:
        raise ValueError(
            "Estimativas calculadas por versões diferentes do método não são comparáveis: "
            f"{inicial.method_version} vs {residual.method_version}."
        )
    reducao = (
        ((inicial.produto - residual.produto) / inicial.produto * 100).quantize(Decimal("0.1"))
        if inicial.produto > 0
        else Decimal("0.0")
    )
    return Comparacao(
        inicial=inicial,
        residual=residual,
        degraus=indice_da_faixa(inicial.band) - indice_da_faixa(residual.band),
        reducao_percentual=reducao,
        residual_tolerabel=residual.band in TOLERAVEIS,
        piorou=residual.produto > inicial.produto,
    )
