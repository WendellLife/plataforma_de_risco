"""Um teste por defeito do acervo legado, com o identificador no nome.

As chamadas passam `regras=` explicitamente: quem escolhe o conjunto de regras é o
catálogo de documentos, e cada teste verifica uma regra por vez.
"""

from typing import Any

from motores.verificador import Severidade, verificar

REGRAS_CADASTRO = ("D-01", "D-03")


def test_d01_fonte_sem_ponto_de_bloqueio_bloqueia() -> None:
    ctx: dict[str, Any] = {
        "machine_uuid": "abc",
        "fontes_sem_bloqueio": [{"uuid": "f1", "rotulo": "Pneumática 0,8 bar"}],
    }
    violacoes = verificar(ctx, regras=REGRAS_CADASTRO)
    assert len(violacoes) == 1
    v = violacoes[0]
    assert v.regra == "D-01"
    assert v.severidade is Severidade.BLOCK
    assert "LOTO" in v.mensagem
    assert v.caminho_correcao.endswith("/energia")


def test_d03_risco_com_medida_sem_residual_bloqueia() -> None:
    ctx: dict[str, Any] = {
        "machine_uuid": "abc",
        "riscos_sem_residual": [{"uuid": "h1", "rotulo": "Zona de prensagem"}],
    }
    violacoes = verificar(ctx, regras=REGRAS_CADASTRO)
    assert [v.regra for v in violacoes] == ["D-03"]
    assert violacoes[0].severidade is Severidade.BLOCK


def test_verificador_devolve_todas_as_violacoes_de_uma_vez() -> None:
    """Regra de produto: o usuário não corrige uma violação por vez."""
    ctx: dict[str, Any] = {
        "machine_uuid": "abc",
        "fontes_sem_bloqueio": [{"uuid": "f1", "rotulo": "Pneumática 0,8 bar"}],
        "riscos_sem_residual": [{"uuid": "h1", "rotulo": "Zona de prensagem"}],
    }
    assert {v.regra for v in verificar(ctx, regras=REGRAS_CADASTRO)} == {"D-01", "D-03"}


def test_contexto_limpo_nao_gera_violacao() -> None:
    assert verificar({"machine_uuid": "abc"}, regras=REGRAS_CADASTRO) == []
