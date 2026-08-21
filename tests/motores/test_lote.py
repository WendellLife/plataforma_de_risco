"""Motor de emissão em lote — triagem antes da fila."""

from __future__ import annotations

import pytest

from motores.lote import (
    LIMITE_POR_LOTE,
    Elegibilidade,
    motivo_de_recusa,
    planejar,
    progresso,
)


def _c(uuid: str, label: str, **extra: object) -> dict[str, object]:
    return {"uuid": uuid, "label": label, **extra}


def test_maquina_sem_bloqueio_entra() -> None:
    plano = planejar("DOC01", [_c("1", "Prensa 40t")])
    assert len(plano.prontas) == 1
    assert plano.itens[0].elegibilidade is Elegibilidade.PRONTA


def test_bloqueada_fica_fora_com_a_regra_nomeada() -> None:
    """"Máquina 47 não entrou" é inútil; "D-01: fonte sem bloqueio" é acionável."""
    plano = planejar(
        "DOC02",
        [_c("2", "Serra fita", bloqueios=["D-01"], detalhe="Fonte pneumática sem ponto de bloqueio")],
    )
    item = plano.itens[0]
    assert item.elegibilidade is Elegibilidade.BLOQUEADA
    assert not item.entra
    assert "D-01" in motivo_de_recusa(item)
    assert "ponto de bloqueio" in motivo_de_recusa(item)


def test_ja_publicada_nao_reemite() -> None:
    plano = planejar("DOC03", [_c("3", "Onduladeira", ja_publicada=True)])
    assert plano.itens[0].elegibilidade is Elegibilidade.JA_PUBLICADA
    assert plano.vazio


def test_template_nao_implementado_e_recusa_explicita() -> None:
    plano = planejar("DOC07", [_c("4", "Qualquer", template_implementado=False)])
    assert plano.itens[0].elegibilidade is Elegibilidade.SEM_TEMPLATE


def test_plano_separa_prontas_de_recusadas() -> None:
    plano = planejar(
        "DOC01",
        [
            _c("1", "A"),
            _c("2", "B", bloqueios=["D-03"]),
            _c("3", "C"),
            _c("4", "D", ja_publicada=True),
        ],
    )
    assert len(plano.prontas) == 2
    assert len(plano.recusadas) == 2
    assert plano.total == 4


def test_recusa_de_pronta_nao_gera_mensagem() -> None:
    plano = planejar("DOC01", [_c("1", "A")])
    assert motivo_de_recusa(plano.itens[0]) == ""


def test_teto_por_lote_e_respeitado() -> None:
    """O limite existe para a estimativa de tempo continuar honesta."""
    candidatas = [_c(str(n), f"M{n}") for n in range(LIMITE_POR_LOTE + 15)]
    plano = planejar("DOC01", candidatas)
    assert len(plano.prontas) == LIMITE_POR_LOTE
    assert plano.excedente == 15


def test_recusadas_nao_consomem_o_teto() -> None:
    candidatas = [_c(str(n), f"M{n}", bloqueios=["D-01"]) for n in range(150)]
    candidatas += [_c("ok", "Pronta")]
    plano = planejar("DOC01", candidatas)
    assert len(plano.prontas) == 1
    assert plano.excedente == 0


def test_estimativa_de_tempo_e_conservadora() -> None:
    plano = planejar("DOC01", [_c(str(n), f"M{n}") for n in range(100)])
    assert plano.minutos_estimados == 20  # 100 × 12 s
    assert plano.minutos_estimados < 30   # dentro do critério CA-10


def test_plano_vazio_quando_nada_e_elegivel() -> None:
    plano = planejar("DOC01", [_c("1", "A", bloqueios=["D-01"])])
    assert plano.vazio


def test_plano_serializa_para_a_tela_e_para_o_snapshot() -> None:
    plano = planejar("DOC01", [_c("1", "A"), _c("2", "B", bloqueios=["D-03"])])
    corpo = plano.as_dict()
    assert corpo["ready"] == 1
    assert corpo["refused"] == 1
    assert corpo["items"][1]["rules"] == ["D-03"]


# --------------------------------------------------------------------------- progresso

def test_progresso_conta_pendentes() -> None:
    p = progresso(total=100, publicados=40, falhos=3)
    assert p.pendentes == 57
    assert not p.concluido
    assert p.percentual == 43


def test_progresso_concluido_com_falhas() -> None:
    p = progresso(total=10, publicados=8, falhos=2)
    assert p.concluido
    assert p.percentual == 100


def test_progresso_de_lote_vazio_nao_divide_por_zero() -> None:
    assert progresso(total=0, publicados=0, falhos=0).percentual == 100


def test_progresso_nunca_tem_pendente_negativo() -> None:
    p = progresso(total=5, publicados=4, falhos=3)
    assert p.pendentes == 0
