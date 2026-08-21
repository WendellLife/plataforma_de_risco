from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from motores.sincronizacao import (
    Conflito,
    Falha,
    ResultadoLote,
    StatusLote,
    classificar,
    conferir_relogio,
    ordenar_registros,
)
from motores.sincronizacao.relogio import SemFusoHorario


def test_ordem_de_chegada_e_irrelevante() -> None:
    """O aparelho não orquestra sequência: o servidor resolve a dependência."""
    entrada = [
        {"type": "photo", "client_uuid": "3"},
        {"type": "item_result", "client_uuid": "2"},
        {"type": "field_hazard", "client_uuid": "1"},
    ]
    assert [r["client_uuid"] for r in ordenar_registros(entrada)] == ["1", "2", "3"]


def test_tipo_desconhecido_vai_para_o_fim_sem_quebrar() -> None:
    entrada = [{"type": "coisa_nova", "client_uuid": "z"}, {"type": "item_result", "client_uuid": "a"}]
    assert [r["client_uuid"] for r in ordenar_registros(entrada)] == ["a", "z"]


@pytest.mark.parametrize(
    ("aplicados", "falhas", "conflitos", "esperado"),
    [
        (0, 0, 0, StatusLote.EMPTY),
        (3, 0, 0, StatusLote.APPLIED),
        (2, 1, 0, StatusLote.PARTIAL),
        (2, 0, 1, StatusLote.PARTIAL),
        (0, 2, 0, StatusLote.REJECTED),
        (0, 0, 2, StatusLote.REJECTED),
    ],
)
def test_classificacao_do_lote(aplicados: int, falhas: int, conflitos: int, esperado: StatusLote) -> None:
    assert classificar(aplicados=aplicados, falhas=falhas, conflitos=conflitos) is esperado


def test_conflito_nao_conta_como_falha() -> None:
    """Falha o aparelho corrige; conflito exige decisão humana. São contagens distintas."""
    r = ResultadoLote(client_batch_uuid="x", applied=1)
    r.conflicts.append(Conflito(client_uuid="a", kind="checklist_item", message="colidiu"))
    assert r.failed == 0
    assert r.status is StatusLote.PARTIAL
    corpo = r.as_dict()
    assert corpo["failed"] == 0
    assert len(corpo["conflict_report"]) == 1


def test_resposta_do_contrato_tem_as_chaves_prometidas() -> None:
    r = ResultadoLote(client_batch_uuid="6d0c")
    r.applied = 2
    r.failures.append(Falha(client_uuid="a3", code="validation_error", message="zone inválida"))
    corpo = r.as_dict()
    assert set(corpo) >= {
        "client_batch_uuid", "status", "applied", "failed", "failures", "conflict_report"
    }
    assert corpo["failures"][0]["code"] == "validation_error"


def test_desvio_de_relogio_tolerado() -> None:
    recebido = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    d = conferir_relogio(informado=recebido + timedelta(minutes=5), recebido=recebido)
    assert d.tolerado


def test_desvio_de_relogio_acima_do_limite_vira_aviso() -> None:
    recebido = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    d = conferir_relogio(informado=recebido + timedelta(minutes=40), recebido=recebido)
    assert not d.tolerado
    assert "adiantado" in d.mensagem
    assert "40 min" in d.mensagem


def test_data_sem_fuso_e_recusada() -> None:
    """Data sem fuso não identifica instante — e data de coleta é conteúdo de laudo."""
    with pytest.raises(SemFusoHorario):
        conferir_relogio(
            informado=datetime(2026, 8, 14, 12, 0), recebido=datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
        )
