from __future__ import annotations

from decimal import Decimal

import pytest

from motores.hrn import Band, Fatores, Resultado, comparar, estimar


def _r(produto: str, band: Band, versao: str = "2.1") -> Resultado:
    from motores.hrn import ROTULOS

    return Resultado(
        produto=Decimal(produto), band=band, rotulo=ROTULOS[band], method_version=versao
    )


def test_reducao_percentual_e_degraus() -> None:
    c = comparar(_r("400", Band.VERY_HIGH), _r("40", Band.SIGNIFICANT))
    assert c.reducao_percentual == Decimal("90.0")
    assert c.degraus == 2
    assert c.melhorou
    assert not c.piorou


def test_residual_fora_de_faixa_toleravel_exige_decisao() -> None:
    c = comparar(_r("900", Band.EXTREME), _r("80", Band.HIGH))
    assert not c.residual_tolerabel
    assert c.exige_decisao


def test_residual_em_faixa_toleravel_nao_exige_decisao() -> None:
    c = comparar(_r("900", Band.EXTREME), _r("8", Band.LOW))
    assert c.residual_tolerabel
    assert not c.exige_decisao


def test_residual_pior_que_inicial_e_sinalizado() -> None:
    c = comparar(_r("10", Band.LOW), _r("120", Band.VERY_HIGH))
    assert c.piorou
    assert c.reducao_percentual < 0
    assert c.degraus < 0


def test_versoes_de_metodo_diferentes_nao_sao_comparaveis() -> None:
    """Dois números da mesma escala não significam a mesma coisa (Espec 01, item 5)."""
    with pytest.raises(ValueError, match="versões diferentes"):
        comparar(_r("400", Band.VERY_HIGH), _r("40", Band.SIGNIFICANT, versao="1.0"))


def test_comparacao_usa_o_resultado_do_motor() -> None:
    inicial = estimar(Fatores(lo=Decimal("5"), fe=Decimal("2.5"), dph=Decimal("15"), np=Decimal("2")))
    residual = estimar(Fatores(lo=Decimal("1"), fe=Decimal("1"), dph=Decimal("2"), np=Decimal("2")))
    c = comparar(inicial, residual)
    assert inicial.produto == Decimal("375.000")
    assert residual.produto == Decimal("4.000")
    assert c.melhorou and c.residual_tolerabel
