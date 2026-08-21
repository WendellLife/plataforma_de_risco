"""Sprint 7 — armazenamento do artefato publicado.

O binário publicado é prova: chave estável, integridade conferível, sem sobrescrita.
"""

from __future__ import annotations

import hashlib

import pytest
from django.test import override_settings

from apps.documentos import armazenamento
from apps.documentos.integridade import Veredito, conferir

pytestmark = pytest.mark.django_db


class VersaoFalsa:
    """Dublê: a conferência de integridade não precisa de banco."""

    def __init__(self, pdf_key: str = "", pdf_sha256: str = "") -> None:
        self.pdf_key = pdf_key
        self.pdf_sha256 = pdf_sha256


@pytest.fixture
def bucket(tmp_path, settings):  # noqa: ANN001, ANN201
    settings.STORAGES = {
        **settings.STORAGES,
        "documentos": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    return tmp_path


def test_chave_carrega_tenant_documento_versao_e_hash() -> None:
    chave = armazenamento.chave_de(
        tenant_id=7, documento_uuid="abc-123", versao=2, digest="deadbeefcafe0000"
    )
    assert chave == "documentos/7/abc-123/v2-deadbeefcafe.pdf"


def test_guardar_devolve_hash_e_tamanho(bucket) -> None:  # noqa: ANN001
    conteudo = b"%PDF-1.7 conteudo de teste"
    a = armazenamento.guardar(
        tenant_id=1, documento_uuid="doc", versao=1, conteudo=conteudo
    )
    assert a.sha256 == hashlib.sha256(conteudo).hexdigest()
    assert a.bytes_gravados == len(conteudo)
    assert armazenamento.existe(a.chave)
    assert armazenamento.ler(a.chave) == conteudo


def test_guardar_duas_vezes_o_mesmo_conteudo_nao_duplica(bucket) -> None:  # noqa: ANN001
    """Recompor a mesma versão é idempotente — não cria arquivo novo nem sobrescreve."""
    conteudo = b"%PDF identico"
    primeira = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=conteudo)
    segunda = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=conteudo)
    assert primeira.chave == segunda.chave
    assert len(list((bucket / "documentos" / "1" / "doc").iterdir())) == 1


def test_conteudo_diferente_gera_chave_diferente(bucket) -> None:  # noqa: ANN001
    """Bytes diferentes NUNCA sobrescrevem prova já gravada."""
    a = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"versao A")
    b = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"versao B")
    assert a.chave != b.chave
    assert armazenamento.existe(a.chave) and armazenamento.existe(b.chave)


def test_tenants_diferentes_nunca_compartilham_prefixo(bucket) -> None:  # noqa: ANN001
    a = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"x")
    b = armazenamento.guardar(tenant_id=2, documento_uuid="doc", versao=1, conteudo=b"x")
    assert a.chave.startswith("documentos/1/")
    assert b.chave.startswith("documentos/2/")


def test_sha256_do_arquivo_recalcula_do_binario_guardado(bucket) -> None:  # noqa: ANN001
    a = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"prova")
    assert armazenamento.sha256_do_arquivo(a.chave) == a.sha256


def test_integridade_confere(bucket) -> None:  # noqa: ANN001
    a = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"prova")
    c = conferir(VersaoFalsa(pdf_key=a.chave, pdf_sha256=a.sha256))
    assert c.veredito is Veredito.CONFERE
    assert not c.incidente


def test_integridade_acusa_binario_ausente(bucket) -> None:  # noqa: ANN001
    c = conferir(VersaoFalsa(pdf_key="documentos/1/doc/v1-000000000000.pdf", pdf_sha256="a" * 64))
    assert c.veredito is Veredito.AUSENTE
    assert c.incidente


def test_integridade_acusa_binario_trocado(bucket) -> None:  # noqa: ANN001
    """Arquivo alterado por fora do sistema é incidente, não erro de tela."""
    a = armazenamento.guardar(tenant_id=1, documento_uuid="doc", versao=1, conteudo=b"original")
    caminho = bucket / a.chave
    caminho.write_bytes(b"adulterado")
    c = conferir(VersaoFalsa(pdf_key=a.chave, pdf_sha256=a.sha256))
    assert c.veredito is Veredito.DIVERGENTE
    assert c.incidente


def test_versao_sem_pdf_nao_e_incidente(bucket) -> None:  # noqa: ANN001
    c = conferir(VersaoFalsa())
    assert c.veredito is Veredito.NAO_COMPOSTO
    assert not c.incidente


@override_settings(DOCUMENTS_BUCKET="")
def test_sem_bucket_nao_ha_url_assinada() -> None:
    assert armazenamento.em_bucket() is False
    assert armazenamento.url_temporaria("documentos/1/doc/v1-abc.pdf") is None


def test_backend_ausente_cai_no_default(settings) -> None:  # noqa: ANN001
    """Configuração incompleta degrada para o default em vez de derrubar a emissão."""
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    assert armazenamento.backend() is not None
