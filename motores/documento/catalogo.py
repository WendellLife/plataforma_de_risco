"""Catálogo de templates de documento.

Fonte única da verdade sobre QUAIS documentos existem, quais regras do verificador
cada um precisa passar e por qual trilha cada um é assinado (Espec 03; AD-11).

Domínio puro: nenhuma dependência de Django. O app apps.documentos consulta este
catálogo; nunca o contrário.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Trilha(StrEnum):
    """Trilha de assinatura — decisão AD-11."""

    A3_NUVEM = "a3_nuvem"      # certificado pessoal do engenheiro: responsabilidade técnica
    ECNPJ_HSM = "ecnpj_hsm"    # certificado da organização em HSM: emissão em lote
    SEM_ASSINATURA = "nenhuma"  # documento operacional, não é peça de responsabilidade


ROTULO_TRILHA: dict[Trilha, str] = {
    Trilha.A3_NUVEM: "A3 em nuvem — engenheiro responsável",
    Trilha.ECNPJ_HSM: "e-CNPJ em HSM — emissão pela organização",
    Trilha.SEM_ASSINATURA: "sem assinatura digital",
}


@dataclass(frozen=True, slots=True)
class TemplateDoc:
    codigo: str
    chave_legada: str
    nome: str
    revisao: int
    trilha: Trilha
    regras: tuple[str, ...]
    secoes: tuple[str, ...]
    implementado: bool = False
    exige_engenheiro: bool = True

    @property
    def rotulo_trilha(self) -> str:
        return ROTULO_TRILHA[self.trilha]


SECOES_DOC01 = (
    "Identificação",
    "Objetivo e escopo",
    "Documentos e normas de referência",
    "Metodologia",
    "Limites da máquina",
    "Fontes de energia",
    "Registro fotográfico",
    "Apreciação por zona de perigo",
    "Consolidação",
    "Conclusão",
    "Responsabilidade técnica",
)

SECOES_DOC02 = (
    "Identificação",
    "Escopo da inspeção de segurança",
    "Condições encontradas",
    "Dispositivos de segurança instalados",
    "Não conformidades por gravidade",
    "Medidas de proteção recomendadas",
    "Conclusão da inspeção",
    "Responsabilidade técnica",
)

SECOES_DOC03 = (
    "Identificação",
    "Base normativa aplicada",
    "Resultado por agrupamento",
    "Itens não conformes",
    "Itens não aplicáveis e justificativas",
    "Índice de conformidade",
    "Encerramento",
)

CATALOGO: dict[str, TemplateDoc] = {
    t.codigo: t
    for t in (
        TemplateDoc(
            codigo="DOC01",
            chave_legada="GR.AR.6.9",
            nome="Análise de Risco",
            revisao=3,
            trilha=Trilha.A3_NUVEM,
            regras=("D-01", "D-03", "D-07", "D-09"),
            secoes=SECOES_DOC01,
            implementado=True,
        ),
        TemplateDoc(
            codigo="DOC02",
            chave_legada="GR.RS.4.2",
            nome="Relatório de Segurança",
            revisao=2,
            trilha=Trilha.A3_NUVEM,
            regras=("D-01", "D-03", "D-07", "D-14"),
            secoes=SECOES_DOC02,
            implementado=True,
        ),
        TemplateDoc(
            codigo="DOC03",
            chave_legada="GR.RC.5.1",
            nome="Relatório de Conformidade",
            revisao=5,
            trilha=Trilha.ECNPJ_HSM,
            regras=("D-05", "D-09", "D-18"),
            secoes=SECOES_DOC03,
            implementado=True,
            exige_engenheiro=False,
        ),
        TemplateDoc("DOC04", "GR.LT.2.0", "Laudo Técnico de Adequação", 2, Trilha.A3_NUVEM,
                    ("D-01", "D-03", "D-05", "D-07"), (), False),
        TemplateDoc("DOC05", "GR.RCT.1.4", "Riscos Categorizados", 1, Trilha.ECNPJ_HSM,
                    ("D-03",), (), False, False),
        TemplateDoc("DOC06", "GR.RR.1.2", "Resumo de Riscos", 1, Trilha.ECNPJ_HSM,
                    ("D-03",), (), False, False),
        TemplateDoc("DOC07", "GR.IM.3.0", "Inventário de Máquinas", 3, Trilha.ECNPJ_HSM,
                    (), (), False, False),
        TemplateDoc("DOC08", "GR.LOTO.2.1", "Procedimento LOTO", 2, Trilha.A3_NUVEM,
                    ("D-01",), (), False),
        TemplateDoc("DOC09", "GR.PL.1.0", "Placa NR-12", 1, Trilha.ECNPJ_HSM,
                    ("D-01",), (), False, False),
        TemplateDoc("DOC10", "GR.APR.2.2", "APR de Atividade", 2, Trilha.A3_NUVEM,
                    (), (), False),
        TemplateDoc("DOC11", "GR.PT.1.1", "Permissão de Trabalho", 1, Trilha.SEM_ASSINATURA,
                    ("D-01",), (), False, False),
        TemplateDoc("DOC12", "GR.PA.2.0", "Plano de Ação", 2, Trilha.ECNPJ_HSM,
                    ("D-03",), (), False, False),
    )
}


def template(codigo: str) -> TemplateDoc:
    try:
        return CATALOGO[codigo]
    except KeyError:
        raise TemplateDesconhecido(f"Template {codigo} não existe no catálogo.") from None


def implementados() -> list[TemplateDoc]:
    return [t for t in CATALOGO.values() if t.implementado]


class TemplateDesconhecido(KeyError):
    """Código de template fora do catálogo."""
