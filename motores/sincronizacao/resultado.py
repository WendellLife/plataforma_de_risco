"""Forma do resultado de um lote de sincronização.

Domínio puro: nenhuma dependência de Django, HTTP ou ORM. Aqui vive o que o contrato
promete ao aparelho — aceitação parcial, motivo por registro e conflito separado de
falha — e a ordem em que os tipos de registro precisam ser aplicados.

Distinção que o contrato faz e que o código precisa manter:

- **Falha** é registro inválido. Não entrou, e o aparelho sabe por quê.
- **Conflito** é registro válido que colide com trabalho feito na web. Não entrou por
  decisão de domínio e aguarda revisão HUMANA — não é erro do aparelho e não deve
  fazer o app tentar de novo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# Ordem de aplicação: o aparelho envia em qualquer ordem, o servidor resolve dependência.
# Foto depende do item que ela ilustra; perigo de campo não depende de nada.
TIPOS_ORDENADOS: tuple[str, ...] = ("field_hazard", "item_result", "photo")


class StatusLote(StrEnum):
    APPLIED = "applied"
    PARTIAL = "partial"
    REJECTED = "rejected"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class Falha:
    client_uuid: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"client_uuid": self.client_uuid, "code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class Conflito:
    client_uuid: str
    kind: str
    message: str
    servidor: str = ""
    aparelho: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "client_uuid": self.client_uuid, "kind": self.kind, "message": self.message,
            "server_value": self.servidor, "device_value": self.aparelho,
        }


@dataclass(slots=True)
class ResultadoLote:
    client_batch_uuid: str
    applied: int = 0
    failures: list[Falha] = field(default_factory=list)
    conflicts: list[Conflito] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    replayed: bool = False

    @property
    def failed(self) -> int:
        return len(self.failures)

    @property
    def status(self) -> StatusLote:
        return classificar(
            aplicados=self.applied, falhas=len(self.failures), conflitos=len(self.conflicts)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "client_batch_uuid": self.client_batch_uuid,
            "status": str(self.status),
            "applied": self.applied,
            "failed": self.failed,
            "failures": [f.as_dict() for f in self.failures],
            "conflict_report": [c.as_dict() for c in self.conflicts],
            "warnings": self.warnings,
            "replayed": self.replayed,
        }


def classificar(*, aplicados: int, falhas: int, conflitos: int) -> StatusLote:
    """Conflito NÃO conta como falha, mas impede declarar o lote inteiramente aplicado."""
    if aplicados == 0 and falhas == 0 and conflitos == 0:
        return StatusLote.EMPTY
    if aplicados == 0:
        return StatusLote.REJECTED
    if falhas or conflitos:
        return StatusLote.PARTIAL
    return StatusLote.APPLIED


def ordenar_registros(registros: list[dict[str, object]]) -> list[dict[str, object]]:
    """Ordem de chegada é irrelevante — o servidor resolve a dependência interna."""
    def chave(r: dict[str, object]) -> int:
        tipo = str(r.get("type", ""))
        return TIPOS_ORDENADOS.index(tipo) if tipo in TIPOS_ORDENADOS else len(TIPOS_ORDENADOS)

    return sorted(registros, key=chave)
