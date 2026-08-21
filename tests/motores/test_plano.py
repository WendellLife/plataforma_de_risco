"""Motor do plano de ação — prazo derivado do risco e adequação pela data do fato."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from motores.plano import (
    PESO_SITUACAO,
    Situacao,
    calcular_adequacao,
    classificar_vencimento,
    prazo_sugerido,
)
from motores.plano.prazo import dias_sugeridos

HOJE = date(2026, 8, 19)


# ------------------------------------------------------------------------------- prazo

@pytest.mark.parametrize(
    ("hrn", "dias"),
    [("2", 180), ("8", 120), ("40", 90), ("80", 45), ("375", 20), ("900", 7), ("5000", 3)],
)
def test_prazo_nasce_da_faixa_de_hrn(hrn: str, dias: int) -> None:
    """Zona de HRN 900 e zona de HRN 8 não podem receber o mesmo prazo por padrão."""
    assert dias_sugeridos(Decimal(hrn)) == dias


def test_risco_maior_tem_prazo_menor() -> None:
    assert dias_sugeridos(Decimal("900")) < dias_sugeridos(Decimal("40"))


def test_sem_hrn_nao_se_inventa_prazo() -> None:
    assert prazo_sugerido(None) is None
    assert dias_sugeridos(None) is None


def test_prazo_sugerido_conta_do_dia_informado() -> None:
    assert prazo_sugerido(Decimal("900"), a_partir_de=HOJE) == date(2026, 8, 26)


# -------------------------------------------------------------------------- vencimento

def test_vencida_e_derivada_da_data_de_hoje() -> None:
    v = classificar_vencimento(prazo=date(2026, 8, 1), hoje=HOJE)
    assert v.situacao is Situacao.VENCIDA
    assert v.dias_restantes == -18
    assert "Vencida há 18 dia" in v.mensagem


def test_a_vencer_dentro_da_janela_de_alerta() -> None:
    v = classificar_vencimento(prazo=date(2026, 8, 29), hoje=HOJE)
    assert v.situacao is Situacao.A_VENCER
    assert v.exige_atencao


def test_fora_da_janela_nao_alarma() -> None:
    assert classificar_vencimento(prazo=date(2026, 12, 1), hoje=HOJE).situacao is Situacao.ABERTA


def test_iniciada_aparece_em_execucao() -> None:
    v = classificar_vencimento(prazo=date(2026, 12, 1), iniciada=True, hoje=HOJE)
    assert v.situacao is Situacao.EM_EXECUCAO


def test_concluida_nunca_e_vencida() -> None:
    """Prazo estourado não reabre ação já cumprida."""
    v = classificar_vencimento(prazo=date(2026, 8, 1), concluida_em=date(2026, 7, 30), hoje=HOJE)
    assert v.situacao is Situacao.CONCLUIDA
    assert not v.exige_atencao


def test_cancelada_precede_qualquer_calculo_de_prazo() -> None:
    v = classificar_vencimento(prazo=date(2026, 8, 1), cancelada=True, hoje=HOJE)
    assert v.situacao is Situacao.CANCELADA


# --------------------------------------------------------------------------- adequação

def test_so_concluida_soma() -> None:
    a = calcular_adequacao(["concluida", "vencida", "aberta", "em_execucao"])
    assert a.concluidas == 1
    assert a.percentual == Decimal("25.0")


def test_cancelada_permanece_no_denominador() -> None:
    """Cancelar não some do histórico — senão bastaria cancelar tudo para chegar a 100%."""
    a = calcular_adequacao(["concluida", "cancelada"])
    assert a.total == 2
    assert a.percentual == Decimal("50.0")
    assert a.canceladas == 1


def test_nao_existe_meia_adequacao() -> None:
    """Diferente do checklist: meio interbloqueio não protege ninguém."""
    assert set(PESO_SITUACAO.values()) == {Decimal("1"), Decimal("0")}


def test_sem_acoes_nao_e_cem_por_cento() -> None:
    a = calcular_adequacao([])
    assert a.sem_acoes
    assert a.percentual == Decimal("0.0")


def test_corte_historico_usa_a_data_do_fato() -> None:
    """Adequação de julho não muda porque alguém digitou em setembro."""
    situacoes = ["concluida", "concluida", "aberta"]
    fatos = [date(2026, 7, 10), date(2026, 9, 2), None]
    julho = calcular_adequacao(situacoes, concluidas_ate=fatos, ate=date(2026, 7, 31))
    setembro = calcular_adequacao(situacoes, concluidas_ate=fatos, ate=date(2026, 9, 30))
    assert julho.concluidas == 1
    assert setembro.concluidas == 2
    assert julho.percentual < setembro.percentual


def test_pendentes_e_o_que_sobra() -> None:
    a = calcular_adequacao(["concluida", "cancelada", "vencida", "aberta"])
    assert a.pendentes == 2
