"""Motor de documentos — catálogo, numeração, consolidação e decisão de publicação.

Sem banco: o motor recebe dicionários. É o que permite testar a regra de publicação
sem construir um parque de máquinas.
"""

from decimal import Decimal
from typing import Any

import pytest

from motores.documento import (
    TemplateDesconhecido,
    Trilha,
    build_context,
    consolidar,
    implementados,
    numerar,
    rotulo_faixa,
    template,
)

ESCOPO_LIMPO: dict[str, Any] = {
    "machine_uuid": "m1",
    "project_uuid": "p1",
    "identificacao": {"maquina": {"identificacao": "01 - Onduladeira"}},
    "responsavel": {"uuid": "e1", "nome": "Wendell", "registro": "CREA SP 5069123456"},
    "art": "SP20260814-0912",
    "riscos": [
        {"faixa_inicial": "high", "hrn_inicial": Decimal("240"),
         "faixa_residual": "low", "hrn_residual": Decimal("9"), "medidas": [{"texto": "x"}]},
    ],
}


def test_catalogo_conhece_os_tres_templates_do_sprint() -> None:
    assert [t.codigo for t in implementados()] == ["DOC01", "DOC02", "DOC03"]


def test_template_desconhecido_falha_alto() -> None:
    with pytest.raises(TemplateDesconhecido):
        template("DOC99")


def test_laudo_e_analise_assinam_por_certificado_pessoal() -> None:
    """AD-11: responsabilidade técnica não é assinada pelo CNPJ."""
    assert template("DOC01").trilha is Trilha.A3_NUVEM
    assert template("DOC04").trilha is Trilha.A3_NUVEM
    assert template("DOC01").exige_engenheiro is True


def test_relatorio_de_conformidade_assina_por_ecnpj() -> None:
    doc03 = template("DOC03")
    assert doc03.trilha is Trilha.ECNPJ_HSM
    assert doc03.exige_engenheiro is False


def test_numeracao_de_secoes_acompanha_o_catalogo() -> None:
    secoes = numerar(template("DOC03").secoes)
    assert [s.numero for s in secoes] == list(range(1, len(secoes) + 1))
    assert secoes[0].slug == "identificacao"
    assert secoes[-1].titulo == "Encerramento"


def test_consolidacao_conta_faixas_antes_e_depois() -> None:
    c = consolidar([
        {"faixa_inicial": "high", "hrn_inicial": 240, "faixa_residual": "low", "hrn_residual": 9},
        {"faixa_inicial": "extreme", "hrn_inicial": 720, "faixa_residual": "significant", "hrn_residual": 30},
        {"faixa_inicial": "significant", "hrn_inicial": 40, "faixa_residual": "", "hrn_residual": None},
    ])
    assert c.total == 3
    assert c.intoleraveis_antes == 2
    assert c.intoleraveis_depois == 0
    assert c.sem_residual == 1
    assert c.maior_hrn_inicial == Decimal("720")
    assert c.reducao_percentual == Decimal("95.8")


def test_consolidacao_sem_estimativa_nao_divide_por_zero() -> None:
    c = consolidar([{"faixa_inicial": "", "faixa_residual": ""}])
    assert c.reducao_percentual == Decimal("0.0")


def test_rotulo_de_faixa_em_portugues() -> None:
    assert rotulo_faixa("unacceptable") == "Inaceitável"
    assert rotulo_faixa("") == ""


def test_escopo_coerente_libera_publicacao() -> None:
    ctx = build_context(escopo=ESCOPO_LIMPO, template=template("DOC01"))
    assert ctx.pode_publicar
    assert ctx.bloqueios == []
    assert ctx.method_versions["hrn"] == "2.1"
    assert ctx.method_versions["template"] == "GR.AR.6.9 rev. 3"


def test_fonte_sem_bloqueio_impede_publicacao_da_analise() -> None:
    escopo = ESCOPO_LIMPO | {
        "fontes_sem_bloqueio": [{"uuid": "f1", "rotulo": "Pneumática 0,8 bar"}]
    }
    ctx = build_context(escopo=escopo, template=template("DOC01"))
    assert not ctx.pode_publicar
    assert [b.regra for b in ctx.bloqueios] == ["D-01"]


def test_aviso_nao_impede_publicacao() -> None:
    ctx = build_context(escopo=ESCOPO_LIMPO | {"maquina_sem_tipo": True},
                        template=template("DOC01"))
    assert ctx.pode_publicar
    assert [a.regra for a in ctx.avisos] == ["D-09"]


def test_cada_template_verifica_somente_as_regras_que_exige() -> None:
    """D-01 trava a análise de risco e não trava o relatório de conformidade."""
    escopo = ESCOPO_LIMPO | {
        "fontes_sem_bloqueio": [{"uuid": "f1", "rotulo": "Pneumática 0,8 bar"}]
    }
    assert not build_context(escopo=escopo, template=template("DOC01")).pode_publicar
    assert build_context(escopo=escopo, template=template("DOC03")).pode_publicar


def test_contexto_expoe_dicionario_para_o_template() -> None:
    payload = build_context(escopo=ESCOPO_LIMPO, template=template("DOC02")).as_dict()
    assert payload["pode_publicar"] is True
    assert payload["template"].codigo == "DOC02"
    assert len(payload["secoes"]) == len(template("DOC02").secoes)
