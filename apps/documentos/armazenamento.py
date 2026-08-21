"""Armazenamento de artefato publicado. Única fronteira com o bucket.

Por que existe uma camada em vez de abrir arquivo direto: o binário publicado é prova.
Precisa de chave estável, integridade verificável e leitura por URL assinada de curta
duração — e o resto da aplicação não pode saber se por trás está disco local ou S3.

Regras desta camada:

1. **A chave carrega o hash.** documentos/<tenant>/<doc>/v<n>-<hash12>.pdf — recompor
   uma versão com bytes diferentes cria arquivo novo em vez de sobrescrever prova.
2. **Nunca sobrescreve.** Se a chave já existe com o mesmo hash, a gravação é no-op.
3. **Sempre com escopo de tenant no caminho.** Chave sem tenant é bug de segurança.
4. **A URL de leitura expira.** Bucket privado; a aplicação assina por poucos minutos.
5. **Integridade é conferível a qualquer momento** por sha256_do_arquivo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import InvalidStorageBackendError, storages

ALIAS = "documentos"


class ArmazenamentoIndisponivel(RuntimeError):
    """O backend configurado não respondeu. Nunca deve derrubar a publicação."""


@dataclass(frozen=True, slots=True)
class Artefato:
    chave: str
    sha256: str
    bytes_gravados: int


def backend():  # noqa: ANN201 - Storage do Django
    try:
        return storages[ALIAS]
    except InvalidStorageBackendError:
        return storages["default"]


def em_bucket() -> bool:
    """Verdadeiro quando o backend é remoto — decide streaming x URL assinada."""
    return bool(getattr(settings, "DOCUMENTS_BUCKET", ""))


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def chave_de(*, tenant_id: int, documento_uuid: str, versao: int, digest: str) -> str:
    return f"documentos/{tenant_id}/{documento_uuid}/v{versao}-{digest[:12]}.pdf"


def guardar(*, tenant_id: int, documento_uuid: str, versao: int, conteudo: bytes) -> Artefato:
    """Grava o binário e devolve a chave. Idempotente por hash."""
    digest = sha256(conteudo)
    chave = chave_de(
        tenant_id=tenant_id, documento_uuid=documento_uuid, versao=versao, digest=digest
    )
    store = backend()
    try:
        if not store.exists(chave):
            store.save(chave, ContentFile(conteudo))
    except Exception as erro:  # noqa: BLE001
        raise ArmazenamentoIndisponivel(f"{type(erro).__name__}: {erro}") from erro
    return Artefato(chave=chave, sha256=digest, bytes_gravados=len(conteudo))


def existe(chave: str) -> bool:
    if not chave:
        return False
    try:
        return backend().exists(chave)
    except Exception:  # noqa: BLE001 - bucket fora do ar não é "arquivo inexistente"
        return False


def abrir(chave: str):  # noqa: ANN201 - File do Django
    return backend().open(chave, "rb")


def ler(chave: str) -> bytes:
    with abrir(chave) as f:
        return f.read()


def sha256_do_arquivo(chave: str) -> str:
    """Recalcula o hash do binário guardado — confere prova contra o banco."""
    h = hashlib.sha256()
    with abrir(chave) as f:
        for bloco in iter(lambda: f.read(1024 * 256), b""):
            h.update(bloco)
    return h.hexdigest()


def url_temporaria(chave: str) -> str | None:
    """URL assinada de curta duração. Devolve None em backend sem assinatura."""
    if not chave or not em_bucket():
        return None
    try:
        return backend().url(chave)
    except Exception:  # noqa: BLE001
        return None


def remover(chave: str) -> None:
    """Limpeza de artefato órfão de composição falha. NUNCA para versão publicada."""
    if chave and existe(chave):
        backend().delete(chave)
