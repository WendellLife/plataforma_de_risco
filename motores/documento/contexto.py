"""Montagem do contexto de renderização.

Contrato (Espec 06): build_context(escopo, template) -> dict pronto para render.
Não renderiza, não grava, não assina, não toca no ORM. Recebe dicionários simples
extraídos por apps.documentos.selectors e devolve dicionários simples.

O que este motor decide, e a camada de template NÃO decide:
  · a numeração das seções;
  · a consolidação de faixas de risco antes e depois das medidas;
  · o índice de conformidade em DOIS denominadores;
  · se o documento pode ser publicado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from motores.hrn import METHOD_VERSION, ROTULOS, Band
from motores.verificador import Severidade, Violacao, verificar

from .catalogo import TemplateDoc

# Faixas acima desta exigem medida de proteção para o documento concluir favoravelmente.
FAIXAS_INTOLERAVEIS: frozenset[str] = frozenset(
    {Band.HIGH, Band.VERY_HIGH, Band.EXTREME, Band.UNACCEPTABLE}
)


@dataclass(frozen=True, slots=True)
class Secao:
    numero: int
    titulo: str
    slug: str


@dataclass(frozen=True, slots=True)
class Consolidacao:
    total: int
    por_faixa_inicial: dict[str, int]
    por_faixa_residual: dict[str, int]
    intoleraveis_antes: int
    intoleraveis_depois: int
    sem_residual: int
    maior_hrn_inicial: Decimal
    maior_hrn_residual: Decimal

    @property
    def reducao_percentual(self) -> Decimal:
        if not self.maior_hrn_inicial:
            return Decimal("0.0")
        delta = self.maior_hrn_inicial - self.maior_hrn_residual
        return (delta / self.maior_hrn_inicial * 100).quantize(Decimal("0.1"))


@dataclass(frozen=True, slots=True)
class Contexto:
    """O que sai deste motor. `pode_publicar` é a única leitura permitida de decisão."""

    template: TemplateDoc
    secoes: list[Secao]
    identificacao: dict[str, Any]
    dados: dict[str, Any]
    consolidacao: Consolidacao | None
    bloqueios: list[Violacao] = field(default_factory=list)
    avisos: list[Violacao] = field(default_factory=list)
    method_versions: dict[str, str] = field(default_factory=dict)

    @property
    def pode_publicar(self) -> bool:
        return not self.bloqueios

    def as_dict(self) -> dict[str, Any]:
        """Forma consumida pelo template Django."""
        return {
            "template": self.template,
            "secoes": self.secoes,
            "ident": self.identificacao,
            "d": self.dados,
            "consolidacao": self.consolidacao,
            "bloqueios": self.bloqueios,
            "avisos": self.avisos,
            "pode_publicar": self.pode_publicar,
            "method_versions": self.method_versions,
        }


def _slug(titulo: str) -> str:
    tabela = str.maketrans("áàâãéêíóôõúüç", "aaaaeeiooouuc")
    limpo = titulo.lower().translate(tabela)
    return "-".join(p for p in "".join(c if c.isalnum() else " " for c in limpo).split())


def numerar(secoes: tuple[str, ...]) -> list[Secao]:
    return [Secao(i, t, _slug(t)) for i, t in enumerate(secoes, start=1)]


def consolidar(riscos: list[dict[str, Any]]) -> Consolidacao:
    """Riscos: [{'faixa_inicial','hrn_inicial','faixa_residual','hrn_residual'}]."""
    inicial: dict[str, int] = {}
    residual: dict[str, int] = {}
    sem_residual = 0
    maior_i = maior_r = Decimal("0")
    for r in riscos:
        fi = r.get("faixa_inicial") or ""
        if fi:
            inicial[fi] = inicial.get(fi, 0) + 1
            maior_i = max(maior_i, Decimal(str(r.get("hrn_inicial") or 0)))
        fr = r.get("faixa_residual") or ""
        if fr:
            residual[fr] = residual.get(fr, 0) + 1
            maior_r = max(maior_r, Decimal(str(r.get("hrn_residual") or 0)))
        else:
            sem_residual += 1
    return Consolidacao(
        total=len(riscos),
        por_faixa_inicial=inicial,
        por_faixa_residual=residual,
        intoleraveis_antes=sum(n for f, n in inicial.items() if f in FAIXAS_INTOLERAVEIS),
        intoleraveis_depois=sum(n for f, n in residual.items() if f in FAIXAS_INTOLERAVEIS),
        sem_residual=sem_residual,
        maior_hrn_inicial=maior_i,
        maior_hrn_residual=maior_r,
    )


def rotulo_faixa(faixa: str) -> str:
    try:
        return ROTULOS[Band(faixa)]
    except ValueError:
        return faixa


def build_context(*, escopo: dict[str, Any], template: TemplateDoc) -> Contexto:
    """Monta o contexto e roda o verificador COM as regras exigidas por este template."""
    violacoes = verificar(escopo, regras=template.regras)
    riscos = escopo.get("riscos", [])
    return Contexto(
        template=template,
        secoes=numerar(template.secoes),
        identificacao=escopo.get("identificacao", {}),
        dados=escopo,
        consolidacao=consolidar(riscos) if riscos else None,
        bloqueios=[v for v in violacoes if v.severidade is Severidade.BLOCK],
        avisos=[v for v in violacoes if v.severidade is Severidade.WARN],
        method_versions={
            "hrn": METHOD_VERSION,
            "template": f"{template.chave_legada} rev. {template.revisao}",
        },
    )
