"""Verificador de coerência.

Executa antes de toda publicação (Espec 01, item 7). Cada regra tem o identificador
do defeito observado no acervo legado, e cada regra tem um teste em
tests/defeitos/ com esse identificador no nome.

Três invariantes do verificador:

1. Devolve TODAS as violações de uma vez — o usuário nunca corrige em série.
2. Toda violação carrega caminho de correção; mensagem sem destino é inútil.
3. O motor não sabe o que é um documento. Quem escolhe as regras é o catálogo.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severidade(StrEnum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: str
    severidade: Severidade
    mensagem: str
    entidade: dict[str, Any] = field(default_factory=dict)
    caminho_correcao: str = ""

    @property
    def bloqueia(self) -> bool:
        return self.severidade is Severidade.BLOCK


Regra = Callable[[dict[str, Any]], list[Violacao]]
_REGRAS: dict[str, Regra] = {}
TITULOS: dict[str, str] = {}


def regra(codigo: str, titulo: str = "") -> Callable[[Regra], Regra]:
    def _registrar(fn: Regra) -> Regra:
        _REGRAS[codigo] = fn
        TITULOS[codigo] = titulo or (fn.__doc__ or "").strip().splitlines()[0]
        return fn

    return _registrar


@regra("D-01", "Fonte de energia sem ponto de bloqueio")
def fonte_sem_ponto_de_bloqueio(ctx: dict[str, Any]) -> list[Violacao]:
    """Fonte de energia cadastrada sem ponto de bloqueio bloqueia LOTO e laudo."""
    return [
        Violacao(
            regra="D-01",
            severidade=Severidade.BLOCK,
            mensagem=(
                f"Fonte {fonte['rotulo']} sem ponto de bloqueio — "
                "o procedimento LOTO não pode ser emitido."
            ),
            entidade={"type": "energy_source", "uuid": fonte["uuid"], "label": fonte["rotulo"]},
            caminho_correcao=f"/maquinas/{ctx['machine_uuid']}/energia",
        )
        for fonte in ctx.get("fontes_sem_bloqueio", [])
    ]


@regra("D-03", "Medida proposta sem risco residual")
def risco_sem_residual(ctx: dict[str, Any]) -> list[Violacao]:
    """Medida de proteção proposta exige reestimativa de HRN."""
    return [
        Violacao(
            regra="D-03",
            severidade=Severidade.BLOCK,
            mensagem=f"Risco “{risco['rotulo']}” tem medida proposta sem HRN residual recalculado.",
            entidade={"type": "hazard", "uuid": risco["uuid"], "label": risco["rotulo"]},
            caminho_correcao=f"/hazards/{risco['uuid']}/estimativas",
        )
        for risco in ctx.get("riscos_sem_residual", [])
    ]


@regra("D-05", "Checklist não encerrado")
def checklist_aberto(ctx: dict[str, Any]) -> list[Violacao]:
    """Índice de conformidade só é publicável a partir de checklist encerrado."""
    return [
        Violacao(
            regra="D-05",
            severidade=Severidade.BLOCK,
            mensagem=(
                f"Checklist {c['norma']} está em “{c['situacao']}” com {c['pendentes']} "
                "item(ns) sem resposta — o índice de conformidade não pode ser publicado."
            ),
            entidade={"type": "assessment", "uuid": c["uuid"], "label": c["norma"]},
            caminho_correcao=f"/checklists/{c['uuid']}",
        )
        for c in ctx.get("checklists_abertos", [])
    ]


@regra("D-07", "Responsabilidade técnica incompleta")
def responsabilidade_incompleta(ctx: dict[str, Any]) -> list[Violacao]:
    """Peça de responsabilidade exige engenheiro com registro no conselho e ART."""
    violacoes: list[Violacao] = []
    resp = ctx.get("responsavel") or {}
    uuid_maquina = ctx.get("machine_uuid", "")
    if not resp.get("nome"):
        violacoes.append(
            Violacao(
                regra="D-07",
                severidade=Severidade.BLOCK,
                mensagem="Nenhum engenheiro responsável vinculado ao projeto desta máquina.",
                entidade={"type": "project", "uuid": ctx.get("project_uuid", "")},
                caminho_correcao=f"/maquinas/{uuid_maquina}/projeto",
            )
        )
    elif not resp.get("registro"):
        violacoes.append(
            Violacao(
                regra="D-07",
                severidade=Severidade.BLOCK,
                mensagem=(
                    f"{resp['nome']} está vinculado como responsável técnico sem registro "
                    "no conselho profissional."
                ),
                entidade={"type": "person", "uuid": resp.get("uuid", ""), "label": resp["nome"]},
                caminho_correcao=f"/pessoas/{resp.get('uuid', '')}",
            )
        )
    if not ctx.get("art"):
        violacoes.append(
            Violacao(
                regra="D-07",
                severidade=Severidade.BLOCK,
                mensagem="Projeto sem número de ART registrado — o documento não pode ser assinado.",
                entidade={"type": "project", "uuid": ctx.get("project_uuid", "")},
                caminho_correcao=f"/maquinas/{uuid_maquina}/projeto",
            )
        )
    return violacoes


@regra("D-09", "Máquina sem tipo definido")
def maquina_sem_tipo(ctx: dict[str, Any]) -> list[Violacao]:
    """Sem tipo de máquina não há como validar a aplicabilidade dos anexos da NR-12."""
    if not ctx.get("maquina_sem_tipo"):
        return []
    return [
        Violacao(
            regra="D-09",
            severidade=Severidade.WARN,
            mensagem=(
                "Máquina sem tipo definido — os anexos da NR-12 citados não passam pela "
                "validação de aplicabilidade (defeito D-02)."
            ),
            entidade={"type": "machine", "uuid": ctx.get("machine_uuid", "")},
            caminho_correcao=f"/maquinas/{ctx.get('machine_uuid', '')}",
        )
    ]


@regra("D-14", "Certificado de dispositivo vencido")
def certificado_vencido(ctx: dict[str, Any]) -> list[Violacao]:
    """Dispositivo de segurança com certificado vencido é declarado, não omitido."""
    return [
        Violacao(
            regra="D-14",
            severidade=Severidade.WARN,
            mensagem=(
                f"{c['rotulo']}: certificado {c['certificado']} venceu em {c['validade']} — "
                "o relatório declara o vencimento."
            ),
            entidade={"type": "component", "uuid": c["uuid"], "label": c["rotulo"]},
            caminho_correcao=f"/maquinas/{ctx.get('machine_uuid', '')}/componentes",
        )
        for c in ctx.get("certificados_vencidos", [])
    ]


@regra("D-18", "Item não aplicável sem justificativa")
def na_sem_justificativa(ctx: dict[str, Any]) -> list[Violacao]:
    """Item marcado como não aplicável nunca desaparece: exige justificativa."""
    return [
        Violacao(
            regra="D-18",
            severidade=Severidade.BLOCK,
            mensagem=(
                f"Item {i['library_key']} respondido como não aplicável sem justificativa — "
                "excluir item da base sem motivo altera o denominador do índice."
            ),
            entidade={"type": "item_result", "uuid": i["uuid"], "label": i["library_key"]},
            caminho_correcao=f"/checklists/{i['assessment_uuid']}#{i['library_key']}",
        )
        for i in ctx.get("itens_na_sem_justificativa", [])
    ]


def verificar(
    contexto: dict[str, Any], regras: Iterable[str] | None = None
) -> list[Violacao]:
    """Roda as regras pedidas (ou todas) e devolve TODAS as violações de uma vez.

    `regras` vem do catálogo de documentos: cada template declara o que exige.
    """
    codigos = list(regras) if regras is not None else list(_REGRAS)
    violacoes: list[Violacao] = []
    for codigo in codigos:
        fn = _REGRAS.get(codigo)
        if fn is None:
            raise RegraDesconhecida(f"Regra {codigo} não está registrada no verificador.")
        violacoes.extend(fn(contexto))
    return sorted(violacoes, key=lambda v: (v.severidade is Severidade.WARN, v.regra))


def registradas() -> tuple[str, ...]:
    return tuple(_REGRAS)


class RegraDesconhecida(KeyError):
    """Template pediu uma regra que não existe."""
