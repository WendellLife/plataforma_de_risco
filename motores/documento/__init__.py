"""Motor de documentos — Sprint 5.

Contrato: build_context(escopo, template) -> Contexto pronto para renderização.
Não renderiza, não grava, não assina.
"""

from .catalogo import (
    CATALOGO,
    ROTULO_TRILHA,
    TemplateDesconhecido,
    TemplateDoc,
    Trilha,
    implementados,
    template,
)
from .contexto import (
    FAIXAS_INTOLERAVEIS,
    Consolidacao,
    Contexto,
    Secao,
    build_context,
    consolidar,
    numerar,
    rotulo_faixa,
)

__all__ = [
    "CATALOGO",
    "FAIXAS_INTOLERAVEIS",
    "ROTULO_TRILHA",
    "Consolidacao",
    "Contexto",
    "Secao",
    "TemplateDesconhecido",
    "TemplateDoc",
    "Trilha",
    "build_context",
    "consolidar",
    "implementados",
    "numerar",
    "rotulo_faixa",
    "template",
]
