"""Dois denominadores e o defeito D-18."""

from decimal import Decimal

import pytest

from motores.conformidade import Resposta, ResultadoItem, calcular


def _respostas() -> list[Resposta]:
    return [
        Resposta("NR12-001", ResultadoItem.COMPLIANT),
        Resposta("NR12-002", ResultadoItem.NON_COMPLIANT),
        Resposta("NR12-003", ResultadoItem.PARTIAL),
        Resposta("NR12-004", ResultadoItem.NOT_APPLICABLE, "Máquina sem sistema hidráulico."),
    ]


def test_dois_denominadores_sao_diferentes() -> None:
    c = calcular(_respostas(), base_fixa=74)
    assert c.avaliados == 3
    assert c.conformes == Decimal("1.5")
    assert c.percentual_avaliados == Decimal("50.0")
    assert c.percentual_base_fixa == Decimal("2.0")
    assert c.percentual_base_fixa != c.percentual_avaliados


def test_nao_aplicavel_nao_desaparece() -> None:
    c = calcular(_respostas(), base_fixa=74)
    assert c.nao_aplicaveis == 1
    assert c.base_fixa == 74  # o denominador fixo não encolhe


def test_d18_nao_aplicavel_sem_justificativa_e_recusado() -> None:
    with pytest.raises(ValueError, match="D-18"):
        Resposta("NR12-041", ResultadoItem.NOT_APPLICABLE)


def test_base_vazia_nao_divide_por_zero() -> None:
    c = calcular([], base_fixa=0)
    assert c.percentual_base_fixa == Decimal("0.0")
    assert c.percentual_avaliados == Decimal("0.0")
