"""Filtros de apresentação dos documentos. Nenhuma regra de negócio aqui."""

from __future__ import annotations

from django import template

from motores.documento import FAIXAS_INTOLERAVEIS

register = template.Library()

_MEDIAS = {"significant"}


@register.filter
def classe_faixa(faixa: str) -> str:
    """Classe visual da faixa de HRN. A decisão de gravidade vem do motor."""
    if not faixa:
        return "faixa--vazio"
    if faixa in FAIXAS_INTOLERAVEIS:
        return "faixa--alto"
    if faixa in _MEDIAS:
        return "faixa--medio"
    return "faixa--ok"


@register.filter
def classe_resultado(resultado: str) -> str:
    return {
        "Conforme": "faixa--ok",
        "Parcial": "faixa--medio",
        "Não conforme": "faixa--alto",
        "Não aplicável": "faixa--vazio",
    }.get(resultado, "faixa--vazio")


@register.filter
def numero(valor: object) -> str:
    """Número sem zeros à direita — 12.000 imprime 12."""
    if valor in (None, ""):
        return "—"
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"{f:g}".replace(".", ",")


@register.filter
def secao(secoes: list, indice: int) -> str:
    """Título numerado da n-ésima seção, para o corpo casar com o sumário."""
    try:
        s = secoes[indice - 1]
    except (IndexError, TypeError):
        return ""
    return f"{s.numero}. {s.titulo}"
