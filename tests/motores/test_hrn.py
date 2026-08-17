"""Tabela de casos do motor de HRN, com foco nos LIMITES de cada faixa."""

from decimal import Decimal

import pytest

from motores.hrn import METHOD_VERSION, Band, Fatores, estimar, faixa_de


@pytest.mark.parametrize(
    ("produto", "band"),
    [
        ("0.5", Band.NEGLIGIBLE),
        ("1", Band.NEGLIGIBLE),      # limite superior
        ("1.001", Band.VERY_LOW),
        ("5", Band.VERY_LOW),
        ("5.001", Band.LOW),
        ("10", Band.LOW),
        ("10.001", Band.SIGNIFICANT),
        ("50", Band.SIGNIFICANT),
        ("50.001", Band.HIGH),
        ("100", Band.HIGH),
        ("100.001", Band.VERY_HIGH),
        ("500", Band.VERY_HIGH),
        ("500.001", Band.EXTREME),
        ("1000", Band.EXTREME),
        ("1000.001", Band.UNACCEPTABLE),
        ("99999", Band.UNACCEPTABLE),
    ],
)
def test_faixa_por_limite(produto: str, band: Band) -> None:
    assert faixa_de(Decimal(produto)) is band


def test_produto_e_versao_do_metodo() -> None:
    r = estimar(Fatores(lo=Decimal("5"), fe=Decimal("4"), dph=Decimal("8"), np=Decimal("2")))
    assert r.produto == Decimal("320.000")
    assert r.band is Band.VERY_HIGH
    assert r.method_version == METHOD_VERSION


def test_residual_menor_que_inicial() -> None:
    inicial = estimar(Fatores(lo=Decimal("5"), fe=Decimal("4"), dph=Decimal("8"), np=Decimal("2")))
    residual = estimar(Fatores(lo=Decimal("1.5"), fe=Decimal("2.5"), dph=Decimal("4"), np=Decimal("2")))
    assert residual.produto < inicial.produto
    assert residual.band is Band.SIGNIFICANT


@pytest.mark.parametrize("fator", ["lo", "fe", "dph", "np"])
def test_fator_nao_positivo_e_recusado(fator: str) -> None:
    valores = {"lo": Decimal("2"), "fe": Decimal("2"), "dph": Decimal("2"), "np": Decimal("2")}
    valores[fator] = Decimal("0")
    with pytest.raises(ValueError):
        Fatores(**valores)  # type: ignore[arg-type]


def test_float_e_recusado() -> None:
    with pytest.raises(TypeError):
        Fatores(lo=1.5, fe=Decimal("2"), dph=Decimal("2"), np=Decimal("2"))  # type: ignore[arg-type]
