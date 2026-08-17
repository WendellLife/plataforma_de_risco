"""Motor de estimativa de risco HRN.

Domínio puro: nenhuma dependência de Django, ORM, HTTP ou armazenamento.
Toda estimativa gravada no banco carrega METHOD_VERSION — dois documentos só são
comparáveis se calculados pela mesma versão (Espec 01, item 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

METHOD_VERSION = "2.1"


class Band(StrEnum):
    NEGLIGIBLE = "negligible"
    VERY_LOW = "very_low"
    LOW = "low"
    SIGNIFICANT = "significant"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"
    UNACCEPTABLE = "unacceptable"


# Limite superior inclusivo de cada faixa. None = sem teto.
FAIXAS: tuple[tuple[Band, Decimal | None], ...] = (
    (Band.NEGLIGIBLE, Decimal("1")),
    (Band.VERY_LOW, Decimal("5")),
    (Band.LOW, Decimal("10")),
    (Band.SIGNIFICANT, Decimal("50")),
    (Band.HIGH, Decimal("100")),
    (Band.VERY_HIGH, Decimal("500")),
    (Band.EXTREME, Decimal("1000")),
    (Band.UNACCEPTABLE, None),
)

ROTULOS: dict[Band, str] = {
    Band.NEGLIGIBLE: "Desprezível",
    Band.VERY_LOW: "Muito baixo",
    Band.LOW: "Baixo",
    Band.SIGNIFICANT: "Significante",
    Band.HIGH: "Alto",
    Band.VERY_HIGH: "Muito alto",
    Band.EXTREME: "Extremo",
    Band.UNACCEPTABLE: "Inaceitável",
}


@dataclass(frozen=True, slots=True)
class Fatores:
    """LO x FE x DPH x NP — os quatro fatores da estimativa."""

    lo: Decimal
    fe: Decimal
    dph: Decimal
    np: Decimal

    def __post_init__(self) -> None:
        for nome in ("lo", "fe", "dph", "np"):
            valor = getattr(self, nome)
            if not isinstance(valor, Decimal):
                raise TypeError(f"{nome} precisa ser Decimal, não {type(valor).__name__}")
            if valor <= 0:
                raise ValueError(f"{nome} precisa ser maior que zero")


@dataclass(frozen=True, slots=True)
class Resultado:
    produto: Decimal
    band: Band
    rotulo: str
    method_version: str = METHOD_VERSION


def faixa_de(produto: Decimal) -> Band:
    """Mapeia o produto HRN em uma das oito faixas."""
    for band, teto in FAIXAS:
        if teto is None or produto <= teto:
            return band
    return Band.UNACCEPTABLE  # inalcançável; mantido por clareza


def estimar(fatores: Fatores) -> Resultado:
    produto = (fatores.lo * fatores.fe * fatores.dph * fatores.np).quantize(Decimal("0.001"))
    band = faixa_de(produto)
    return Resultado(produto=produto, band=band, rotulo=ROTULOS[band])
