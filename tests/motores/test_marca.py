"""Motor de identidade visual — o que o white-label pode e o que nunca pode."""

from __future__ import annotations

import pytest

from motores.marca import (
    PADRAO,
    Superficie,
    contraste,
    cor_valida,
    resolver,
    texto_legivel_sobre,
    variaveis_css,
)

CLIENTE = {
    "nome": "Cartonagem Brasil",
    "logo_key": "marcas/1/cartonagem.png",
    "primaria": "#F2C200",
    "secundaria": "#1B3A6B",
}


# ------------------------------------------------------------------ limites do white-label

def test_interface_aceita_marca_do_cliente() -> None:
    m = resolver(superficie=Superficie.INTERFACE, plataforma="Life Laboral", cliente=CLIENTE)
    assert m.nome == "Cartonagem Brasil"
    assert m.primaria == "#F2C200"
    assert not m.co_marca


def test_documento_e_sempre_co_marca() -> None:
    """O emissor técnico não pode desaparecer do laudo que ele assina."""
    m = resolver(superficie=Superficie.DOCUMENTO, plataforma="Life Laboral", cliente=CLIENTE)
    assert m.co_marca
    assert m.emissor == "Life Laboral"


def test_verificacao_publica_ignora_a_marca_do_cliente() -> None:
    """Ela prova autenticidade: parecer material do contratante enfraquece a prova."""
    m = resolver(
        superficie=Superficie.VERIFICACAO_PUBLICA, plataforma="Life Laboral", cliente=CLIENTE
    )
    assert m.nome == "Life Laboral"
    assert m.logo_key == ""
    assert m.primaria == PADRAO["primaria"]


def test_sem_cliente_cai_na_marca_da_plataforma() -> None:
    m = resolver(superficie=Superficie.INTERFACE, plataforma="Life Laboral")
    assert m.nome == "Life Laboral"
    assert m.primaria == PADRAO["primaria"]


# --------------------------------------------------------------------------- robustez

def test_cor_invalida_cai_no_padrao_em_vez_de_quebrar() -> None:
    m = resolver(
        superficie=Superficie.INTERFACE, plataforma="LL",
        cliente={"nome": "X", "primaria": "azul-marinho"},
    )
    assert m.primaria == PADRAO["primaria"]


def test_marca_nunca_volta_parcial() -> None:
    """Meia identidade é pior que nenhuma: todo campo tem valor."""
    m = resolver(superficie=Superficie.INTERFACE, plataforma="LL", cliente={"nome": "X"})
    assert m.primaria and m.secundaria and m.tinta and m.texto_sobre_primaria


@pytest.mark.parametrize(
    ("cor", "valida"),
    [("#fff", True), ("#F2C200", True), ("F2C200", False), ("", False), ("#12", False),
     ("#GGGGGG", False)],
)
def test_validacao_de_cor(cor: str, valida: bool) -> None:
    assert cor_valida(cor) is valida


# --------------------------------------------------------------------------- contraste

def test_texto_sobre_amarelo_fica_escuro() -> None:
    """O cliente escolhe a cor, não o texto sobre ela. Branco no amarelo é ilegível."""
    assert texto_legivel_sobre("#F2C200") == PADRAO["tinta"]


def test_texto_sobre_azul_escuro_fica_branco() -> None:
    assert texto_legivel_sobre("#1B3A6B") == "#ffffff"


def test_cor_de_texto_e_decidida_no_motor() -> None:
    m = resolver(
        superficie=Superficie.INTERFACE, plataforma="LL",
        cliente={"nome": "X", "primaria": "#F2C200"},
    )
    assert m.texto_sobre_primaria == PADRAO["tinta"]
    assert contraste(m.primaria, m.texto_sobre_primaria) >= 3.0


def test_contraste_e_simetrico() -> None:
    assert contraste("#ffffff", "#000000") == contraste("#000000", "#ffffff")


def test_variaveis_css_saem_prontas_para_injetar() -> None:
    m = resolver(superficie=Superficie.INTERFACE, plataforma="LL", cliente=CLIENTE)
    css = variaveis_css(m)
    assert "--brand-primary:#F2C200" in css
    assert "--brand-on-primary:" in css
