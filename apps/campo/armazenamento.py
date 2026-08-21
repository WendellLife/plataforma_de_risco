"""Chaves e URL de envio das fotos de campo.

O aparelho envia o binário DIRETO para o armazenamento: a aplicação não intermedeia
bytes de foto (Espec 08, item 7). Ela só assina uma URL de curta duração e depois
confirma o registro com a chave recebida, no próximo lote.

Reaproveita o backend do alias de armazenamento aberto no Sprint 7. Se um terceiro
consumidor aparecer, essa fronteira sobe para apps/core — hoje seriam duas cópias da
mesma coisa, o que é pior que o import.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.documentos import armazenamento as store

EXTENSOES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


class TipoNaoAceito(ValueError):
    """Só imagem entra por esta porta."""


class ArquivoGrandeDemais(ValueError):
    """Limite de bytes por foto — o aparelho comprime antes de enviar."""


@dataclass(frozen=True, slots=True)
class Presign:
    upload_url: str
    file_key: str
    expires_in: int
    max_bytes: int
    direto: bool  # False = o aparelho precisa enviar pela aplicação (ambiente sem bucket)


def limite_bytes() -> int:
    return int(getattr(settings, "FIELD_PHOTO_MAX_BYTES", 12_000_000))


def chave_de_foto(*, tenant_id: int, device_id: str, client_uuid: str, content_type: str) -> str:
    extensao = EXTENSOES.get(content_type)
    if extensao is None:
        raise TipoNaoAceito(
            f"{content_type} não é um formato de imagem aceito. Use JPEG, PNG, WebP ou HEIC."
        )
    seguro = "".join(c if c.isalnum() or c in "-_" else "-" for c in device_id)[:40]
    return f"campo/{tenant_id}/{seguro}/{client_uuid}.{extensao}"


def presign(
    *, tenant_id: int, device_id: str, client_uuid: str, content_type: str, bytes_: int
) -> Presign:
    if bytes_ > limite_bytes():
        raise ArquivoGrandeDemais(
            f"A foto tem {bytes_} bytes e o limite é {limite_bytes()}. "
            "O aparelho deve comprimir antes de enviar."
        )
    chave = chave_de_foto(
        tenant_id=tenant_id, device_id=device_id, client_uuid=client_uuid,
        content_type=content_type,
    )
    ttl = int(getattr(settings, "FIELD_UPLOAD_TTL", 900))
    url = _url_de_envio(chave, content_type=content_type, ttl=ttl)
    return Presign(
        upload_url=url or "", file_key=chave, expires_in=ttl,
        max_bytes=limite_bytes(), direto=bool(url),
    )


def _url_de_envio(chave: str, *, content_type: str, ttl: int) -> str | None:
    """URL assinada de PUT. None em backend sem assinatura — o dev sobe pela aplicação."""
    if not store.em_bucket():
        return None
    backend = store.backend()
    conexao = getattr(backend, "connection", None)
    bucket = getattr(backend, "bucket_name", "")
    if conexao is None or not bucket:
        return None
    try:
        return conexao.meta.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": chave, "ContentType": content_type},
            ExpiresIn=ttl,
        )
    except Exception:  # noqa: BLE001 - sem assinatura o app cai no envio pela aplicação
        return None


def guardar_direto(*, chave: str, conteudo: bytes) -> int:
    """Recebe a foto pela aplicação. Caminho de exceção: ambiente sem bucket assinável."""
    from django.core.files.base import ContentFile

    backend = store.backend()
    if not backend.exists(chave):
        backend.save(chave, ContentFile(conteudo))
    return len(conteudo)


def existe(chave: str) -> bool:
    return store.existe(chave)
