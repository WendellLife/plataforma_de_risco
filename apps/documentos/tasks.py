"""Fila "documentos" — composição do PDF e emissão em lote."""

from __future__ import annotations

from celery import shared_task
from django.conf import settings

from apps.core.tenancy import usando_tenant

from .enums import RenderStatus


@shared_task(queue="documentos", bind=True, max_retries=3, default_retry_delay=30)
def compor_pdf(self, version_id: int) -> str:  # noqa: ANN001
    """Compõe o PDF de uma versão publicada e o guarda no armazenamento.

    Idempotente: a chave deriva do hash do binário, então recompor não republica nem
    sobrescreve prova. Falha de armazenamento é RETENTADA — o PDF de uma versão
    publicada não pode ficar faltando em silêncio.
    """
    from . import armazenamento
    from .models import DocumentVersion
    from .renderizacao import html_do_documento, pdf_do_html
    from .services import montar

    versao = DocumentVersion.sem_escopo.select_related("document", "document__machine").get(
        pk=version_id
    )
    with usando_tenant(versao.tenant_id):
        try:
            documento = versao.document
            html = html_do_documento(documento=documento, contexto=montar(documento=documento))
            conteudo, paginas = pdf_do_html(html, base_url=str(settings.BASE_DIR))
            artefato = armazenamento.guardar(
                tenant_id=versao.tenant_id,
                documento_uuid=str(documento.public_uuid),
                versao=versao.number,
                conteudo=conteudo,
            )
        except armazenamento.ArmazenamentoIndisponivel as erro:
            _marcar_falha(versao, erro)
            raise self.retry(exc=erro) from erro
        except Exception as erro:  # noqa: BLE001 - a falha precisa ficar visível na tela
            _marcar_falha(versao, erro)
            raise
        versao.pdf_key = artefato.chave
        versao.pdf_sha256 = artefato.sha256
        versao.pdf_bytes = artefato.bytes_gravados
        versao.page_count = paginas
        versao.render_status = RenderStatus.RENDERED
        versao.render_error = ""
        versao.save(
            update_fields=[
                "pdf_key", "pdf_sha256", "pdf_bytes", "page_count",
                "render_status", "render_error",
            ]
        )
    return versao.pdf_key


def _marcar_falha(versao, erro: Exception) -> None:  # noqa: ANN001
    versao.render_status = RenderStatus.FAILED
    versao.render_error = f"{type(erro).__name__}: {erro}"
    versao.save(update_fields=["render_status", "render_error"])


@shared_task(queue="documentos")
def conferir_integridade(version_id: int) -> str:
    """Recalcula o hash do binário guardado e compara com o da publicação."""
    from .integridade import conferir
    from .models import DocumentVersion

    versao = DocumentVersion.sem_escopo.get(pk=version_id)
    with usando_tenant(versao.tenant_id):
        return str(conferir(versao).veredito)

