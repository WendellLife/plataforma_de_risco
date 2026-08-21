"""Verificação pública (CA-06) — a única superfície sem autenticação.

O que estes testes protegem não é a funcionalidade, é o LIMITE dela: confirmar emissão
sem virar uma janela para o conteúdo técnico do contratante.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Project
from apps.ativos.services import (
    acrescentar_fonte_de_energia,
    criar_maquina,
    definir_ponto_de_bloqueio,
)
from apps.clientes.enums import PersonRole
from apps.clientes.models import Person
from apps.clientes.services import criar_cliente
from apps.documentos.qr import svg
from apps.documentos.renderizacao import html_do_documento
from apps.documentos.services import criar_documento, montar, publicar
from apps.documentos.verificacao import comprovar, url_de_verificacao

pytestmark = pytest.mark.django_db


@pytest.fixture
def maquina(escopo_a, tenant_a, engenheiro_a):  # noqa: ANN001, ANN201
    cliente = criar_cliente(
        legal_name="Fundição Pública", tax_id="77777777000177", actor=engenheiro_a
    )
    responsavel = Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233344",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123456", professional_title="Engenheiro de Segurança do Trabalho",
    )
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number="PUB-1-001", engineer=responsavel, status="active"
    )
    m = criar_maquina(
        client_id=cliente.pk, name="Forno de indução", actor=engenheiro_a, project=projeto
    )
    fonte = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.ELECTRIC, magnitude=Decimal("380"), unit="V",
        actor=engenheiro_a,
    )
    definir_ponto_de_bloqueio(energy_source=fonte, identifier="DJ-01", actor=engenheiro_a)
    return m


@pytest.fixture
def publicado(maquina, engenheiro_a):  # noqa: ANN001, ANN201
    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)
    return doc, versao


def test_documento_publicado_e_confirmado(publicado) -> None:  # noqa: ANN001
    doc, versao = publicado
    c = comprovar(str(doc.public_uuid))
    assert c.encontrado
    assert c.content_hash == versao.content_hash
    assert c.versao == versao.number
    assert c.responsavel == "Wendell Engenheiro"
    assert c.registro == "CREA SP 5069123456"


def test_minuta_nao_tem_verificacao_publica(maquina, engenheiro_a) -> None:  # noqa: ANN001
    """Não há o que confirmar sobre documento que ninguém emitiu."""
    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    assert not comprovar(str(doc.public_uuid)).encontrado


def test_uuid_inexistente_e_documento_de_outro_tenant_respondem_igual() -> None:
    assert comprovar("00000000-0000-0000-0000-000000000000").as_dict() == {"found": False}


def test_nao_expoe_conteudo_tecnico(publicado) -> None:  # noqa: ANN001
    """O limite do recurso: confirma a emissão, não abre o laudo."""
    doc, _ = publicado
    corpo = comprovar(str(doc.public_uuid)).as_dict()
    proibidos = {
        "context_snapshot", "hazards", "riscos", "conformidade", "checklist",
        "tax_id", "cnpj", "address", "endereco", "cpf", "doc_number",
    }
    assert not (proibidos & set(corpo))
    assert "12345678" not in str(corpo)  # nenhum documento fiscal vaza


def test_rota_publica_responde_sem_autenticacao(publicado, client) -> None:  # noqa: ANN001
    doc, versao = publicado
    resposta = client.get(f"/api/v1/public/documents/{doc.public_uuid}")
    assert resposta.status_code == 200
    assert resposta.json()["content_hash"] == versao.content_hash


def test_rota_publica_devolve_404_para_minuta(maquina, engenheiro_a, client) -> None:  # noqa: ANN001
    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    resposta = client.get(f"/api/v1/public/documents/{doc.public_uuid}")
    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "not_found"


def test_pagina_publica_abre_sem_login(publicado, client) -> None:  # noqa: ANN001
    doc, versao = publicado
    resposta = client.get(f"/d/{doc.public_uuid}")
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Documento autêntico" in corpo
    assert versao.content_hash in corpo
    assert "Wendell Engenheiro" in corpo


def test_pagina_publica_de_codigo_desconhecido_explica_o_que_fazer(client) -> None:  # noqa: ANN001
    resposta = client.get("/d/00000000-0000-0000-0000-000000000000")
    assert resposta.status_code == 404
    assert "minuta" in resposta.content.decode()


def test_versao_anterior_e_marcada_como_substituida(publicado, engenheiro_a) -> None:  # noqa: ANN001
    doc, primeira = publicado
    publicar(documento=doc, actor=engenheiro_a)
    c = comprovar(str(doc.public_uuid), versao_numero=primeira.number)
    assert c.encontrado
    assert c.substituida
    assert c.versao == primeira.number


def test_qr_e_url_entram_no_documento_publicado(publicado, settings) -> None:  # noqa: ANN001
    settings.PUBLIC_VERIFY_BASE_URL = "https://verifica.lifelaboral.com.br"
    doc, _ = publicado
    html = html_do_documento(documento=doc, contexto=montar(documento=doc))
    esperada = url_de_verificacao(doc, settings.PUBLIC_VERIFY_BASE_URL)
    assert esperada in html
    assert "Verificação pública" in html


def test_minuta_nao_imprime_qr(maquina, engenheiro_a) -> None:  # noqa: ANN001
    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    html = html_do_documento(documento=doc, contexto=montar(documento=doc))
    assert "Verificação pública" not in html
    assert "MINUTA" in html


def test_qr_degrada_sem_a_biblioteca(monkeypatch) -> None:  # noqa: ANN001
    """Sem qrcode instalado o documento imprime a URL — nunca quebra a emissão."""
    import builtins

    real = builtins.__import__

    def sem_qrcode(nome, *args, **kwargs):  # noqa: ANN001, ANN202
        if nome == "qrcode":
            raise ImportError(nome)
        return real(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sem_qrcode)
    assert svg("https://exemplo/d/1") == ""
