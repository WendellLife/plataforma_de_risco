"""Conferência de integridade do artefato publicado.

Duas provas independentes por versão: o hash do CONTEXTO (o que o documento afirma) e o
hash do BINÁRIO (o arquivo entregue). Divergência em qualquer uma delas é incidente,
não é erro de tela — por isso o resultado é tipado e aparece na ficha do documento.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from . import armazenamento


class Veredito(StrEnum):
    CONFERE = "confere"
    AUSENTE = "ausente"
    DIVERGENTE = "divergente"
    NAO_COMPOSTO = "nao_composto"


ROTULOS: dict[Veredito, str] = {
    Veredito.CONFERE: "Binário confere com o hash registrado na publicação",
    Veredito.AUSENTE: "O arquivo não está no armazenamento",
    Veredito.DIVERGENTE: "O binário guardado NÃO corresponde ao hash da publicação",
    Veredito.NAO_COMPOSTO: "Versão publicada e ainda sem PDF composto",
}


@dataclass(frozen=True, slots=True)
class Conferencia:
    veredito: Veredito
    esperado: str
    encontrado: str

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.veredito]

    @property
    def incidente(self) -> bool:
        return self.veredito in (Veredito.AUSENTE, Veredito.DIVERGENTE)


def conferir(versao) -> Conferencia:  # noqa: ANN001 - DocumentVersion
    esperado = versao.pdf_sha256 or ""
    if not versao.pdf_key or not esperado:
        return Conferencia(veredito=Veredito.NAO_COMPOSTO, esperado=esperado, encontrado="")
    if not armazenamento.existe(versao.pdf_key):
        return Conferencia(veredito=Veredito.AUSENTE, esperado=esperado, encontrado="")
    encontrado = armazenamento.sha256_do_arquivo(versao.pdf_key)
    veredito = Veredito.CONFERE if encontrado == esperado else Veredito.DIVERGENTE
    return Conferencia(veredito=veredito, esperado=esperado, encontrado=encontrado)
