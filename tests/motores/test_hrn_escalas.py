from __future__ import annotations

from decimal import Decimal

import pytest

from motores.hrn import FATORES, Band, descritor, escala_visual, indice_da_faixa, opcoes


def test_todo_valor_de_escala_e_positivo_e_decimal() -> None:
    """Fator zero ou negativo violaria a constraint do banco e o motor."""
    for fator in FATORES:
        for opcao in fator.opcoes:
            assert isinstance(opcao.valor, Decimal)
            assert opcao.valor > 0


def test_escalas_sao_monotonicas_crescentes() -> None:
    for fator in FATORES:
        valores = [o.valor for o in fator.opcoes]
        assert valores == sorted(valores), f"escala {fator.sigla} fora de ordem"


def test_valores_unicos_por_escala() -> None:
    for fator in FATORES:
        chaves = [o.chave for o in fator.opcoes]
        assert len(chaves) == len(set(chaves)), f"escala {fator.sigla} tem valor duplicado"


@pytest.mark.parametrize("sigla", ["lo", "fe", "dph", "np"])
def test_descritor_encontra_valor_da_escala(sigla: str) -> None:
    primeira = opcoes(sigla)[0]
    assert descritor(sigla, primeira.valor) == primeira.rotulo


def test_descritor_de_valor_fora_da_escala_devolve_o_numero() -> None:
    """Estimativa gravada por versão anterior do método não some da tela."""
    assert descritor("np", Decimal("3")) == "3"


def test_escala_visual_marca_exatamente_uma_faixa() -> None:
    for produto in ("0.5", "1", "7", "50.001", "999", "5000"):
        linhas = escala_visual(Decimal(produto))
        assert len(linhas) == 8
        assert sum(1 for l in linhas if l["atual"]) == 1


def test_indice_da_faixa_ordena_da_menor_para_a_maior() -> None:
    assert indice_da_faixa(Band.NEGLIGIBLE) == 0
    assert indice_da_faixa(Band.UNACCEPTABLE) == 7
    assert indice_da_faixa(Band.LOW) < indice_da_faixa(Band.HIGH)
