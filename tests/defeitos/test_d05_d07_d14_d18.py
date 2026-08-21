"""Regras do verificador introduzidas no Sprint 5, uma por defeito do acervo."""

from typing import Any

import pytest

from motores.verificador import RegraDesconhecida, Severidade, verificar

CTX_BASE: dict[str, Any] = {"machine_uuid": "m1", "project_uuid": "p1"}


def test_d05_checklist_aberto_bloqueia_indice_de_conformidade() -> None:
    ctx = CTX_BASE | {
        "checklists_abertos": [
            {"uuid": "a1", "norma": "NR-12", "situacao": "Em coleta", "pendentes": 34}
        ]
    }
    (v,) = verificar(ctx, regras=("D-05",))
    assert v.regra == "D-05"
    assert v.severidade is Severidade.BLOCK
    assert "34" in v.mensagem
    assert v.caminho_correcao == "/checklists/a1"


def test_d07_sem_engenheiro_e_sem_art_acumula_dois_bloqueios() -> None:
    violacoes = verificar(CTX_BASE | {"responsavel": {}, "art": ""}, regras=("D-07",))
    assert len(violacoes) == 2
    assert all(v.severidade is Severidade.BLOCK for v in violacoes)


def test_d07_engenheiro_sem_registro_no_conselho_bloqueia() -> None:
    ctx = CTX_BASE | {
        "responsavel": {"uuid": "e1", "nome": "Wendell Engenheiro", "registro": ""},
        "art": "SP20260814-0912",
    }
    (v,) = verificar(ctx, regras=("D-07",))
    assert "registro no conselho" in v.mensagem
    assert v.caminho_correcao == "/pessoas/e1"


def test_d07_responsabilidade_completa_nao_bloqueia() -> None:
    ctx = CTX_BASE | {
        "responsavel": {"uuid": "e1", "nome": "Wendell", "registro": "CREA SP 5069123456"},
        "art": "SP20260814-0912",
    }
    assert verificar(ctx, regras=("D-07",)) == []


def test_d09_maquina_sem_tipo_avisa_mas_nao_bloqueia() -> None:
    (v,) = verificar(CTX_BASE | {"maquina_sem_tipo": True}, regras=("D-09",))
    assert v.severidade is Severidade.WARN
    assert not v.bloqueia


def test_d14_certificado_vencido_avisa() -> None:
    ctx = CTX_BASE | {
        "certificados_vencidos": [
            {"uuid": "c1", "rotulo": "Cortina de luz · Sick",
             "certificado": "BR-SICK-88213", "validade": "31/03/2025"}
        ]
    }
    (v,) = verificar(ctx, regras=("D-14",))
    assert v.severidade is Severidade.WARN
    assert "31/03/2025" in v.mensagem


def test_d18_item_nao_aplicavel_sem_justificativa_bloqueia() -> None:
    ctx = CTX_BASE | {
        "itens_na_sem_justificativa": [
            {"uuid": "i1", "library_key": "NR12-4.2.1", "assessment_uuid": "a1"}
        ]
    }
    (v,) = verificar(ctx, regras=("D-18",))
    assert v.severidade is Severidade.BLOCK
    assert "denominador" in v.mensagem
    assert v.caminho_correcao == "/checklists/a1#NR12-4.2.1"


def test_bloqueio_vem_antes_de_aviso_na_ordenacao() -> None:
    ctx = CTX_BASE | {
        "maquina_sem_tipo": True,
        "itens_na_sem_justificativa": [
            {"uuid": "i1", "library_key": "NR12-4.2.1", "assessment_uuid": "a1"}
        ],
    }
    severidades = [v.severidade for v in verificar(ctx, regras=("D-09", "D-18"))]
    assert severidades == [Severidade.BLOCK, Severidade.WARN]


def test_regra_fora_do_registro_falha_alto() -> None:
    with pytest.raises(RegraDesconhecida):
        verificar(CTX_BASE, regras=("D-99",))
