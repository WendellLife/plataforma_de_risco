"""Planejamento de emissão em lote. Domínio puro.

O que este motor decide, ANTES de qualquer fila: quais máquinas do lote podem ser
emitidas e quais não, com o motivo de cada recusa. Três decisões que evitam que o lote se
torne um botão de esperança:

1. **Triagem antes da fila, não dentro dela.** Enfileirar 100 máquinas e descobrir na
   terceira hora que 40 estavam bloqueadas é desperdício e ansiedade. O plano é calculado
   e MOSTRADO antes de o usuário confirmar.
2. **Recusa nomeia a regra.** "Máquina 47 não entrou" é inútil. "Máquina 47 — D-01: fonte
   pneumática sem ponto de bloqueio" é acionável.
3. **O lote não é transação única.** Uma máquina que falha não desfaz as 99 publicadas.
   Cada emissão é seu próprio ato verificado, com sua própria versão e seu próprio hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# Teto por lote. Existe para que a estimativa de tempo permaneça honesta e para
# que uma chamada acidental não enfileire o parque inteiro (CA-10: 100 máquinas / 30 min).
LIMITE_POR_LOTE = 100


class Elegibilidade(StrEnum):
    PRONTA = "pronta"
    BLOQUEADA = "bloqueada"
    JA_PUBLICADA = "ja_publicada"
    SEM_TEMPLATE = "sem_template"


ROTULOS: dict[Elegibilidade, str] = {
    Elegibilidade.PRONTA: "Pronta para emitir",
    Elegibilidade.BLOQUEADA: "Bloqueada pelo verificador",
    Elegibilidade.JA_PUBLICADA: "Já publicada nesta revisão",
    Elegibilidade.SEM_TEMPLATE: "Template não implementado",
}


@dataclass(frozen=True, slots=True)
class ItemDeLote:
    machine_uuid: str
    machine_label: str
    elegibilidade: Elegibilidade
    regras: tuple[str, ...] = ()
    detalhe: str = ""

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.elegibilidade]

    @property
    def entra(self) -> bool:
        return self.elegibilidade is Elegibilidade.PRONTA

    def as_dict(self) -> dict[str, object]:
        return {
            "machine": self.machine_uuid, "label": self.machine_label,
            "eligibility": str(self.elegibilidade), "rules": list(self.regras),
            "detail": self.detalhe,
        }


@dataclass(slots=True)
class Plano:
    template_code: str
    itens: list[ItemDeLote] = field(default_factory=list)
    excedente: int = 0

    @property
    def prontas(self) -> list[ItemDeLote]:
        return [i for i in self.itens if i.entra]

    @property
    def recusadas(self) -> list[ItemDeLote]:
        return [i for i in self.itens if not i.entra]

    @property
    def total(self) -> int:
        return len(self.itens)

    @property
    def vazio(self) -> bool:
        return not self.prontas

    @property
    def minutos_estimados(self) -> int:
        """Estimativa grosseira e DELIBERADAMENTE conservadora: ~12 s por documento."""
        return max(1, round(len(self.prontas) * 12 / 60))

    def as_dict(self) -> dict[str, object]:
        return {
            "template": self.template_code,
            "ready": len(self.prontas),
            "refused": len(self.recusadas),
            "over_limit": self.excedente,
            "estimated_minutes": self.minutos_estimados,
            "items": [i.as_dict() for i in self.itens],
        }


def motivo_de_recusa(item: ItemDeLote) -> str:
    """Frase pronta para a tela. Nomeia a regra — recusa sem regra não é acionável."""
    if item.entra:
        return ""
    if item.regras:
        return f"{item.machine_label} — {', '.join(item.regras)}: {item.detalhe or item.rotulo}"
    return f"{item.machine_label} — {item.rotulo}"


def planejar(template_code: str, candidatas: list[dict[str, object]]) -> Plano:
    """Monta o plano a partir da triagem já feita pela camada de dados.

    Cada candidata traz: uuid, label, bloqueios (lista de regras), detalhe,
    ja_publicada e template_implementado.
    """
    plano = Plano(template_code=template_code)
    aceitas = 0
    for c in candidatas:
        if not c.get("template_implementado", True):
            elegibilidade = Elegibilidade.SEM_TEMPLATE
        elif c.get("ja_publicada"):
            elegibilidade = Elegibilidade.JA_PUBLICADA
        elif c.get("bloqueios"):
            elegibilidade = Elegibilidade.BLOQUEADA
        else:
            elegibilidade = Elegibilidade.PRONTA

        if elegibilidade is Elegibilidade.PRONTA:
            if aceitas >= LIMITE_POR_LOTE:
                plano.excedente += 1
                continue
            aceitas += 1

        plano.itens.append(
            ItemDeLote(
                machine_uuid=str(c.get("uuid", "")),
                machine_label=str(c.get("label", "")),
                elegibilidade=elegibilidade,
                regras=tuple(c.get("bloqueios") or ()),
                detalhe=str(c.get("detalhe", "")),
            )
        )
    return plano


@dataclass(frozen=True, slots=True)
class Progresso:
    total: int
    publicados: int
    falhos: int

    @property
    def pendentes(self) -> int:
        return max(self.total - self.publicados - self.falhos, 0)

    @property
    def concluido(self) -> bool:
        return self.pendentes == 0

    @property
    def percentual(self) -> int:
        if self.total == 0:
            return 100
        return round((self.publicados + self.falhos) / self.total * 100)


def progresso(*, total: int, publicados: int, falhos: int) -> Progresso:
    return Progresso(total=total, publicados=publicados, falhos=falhos)
