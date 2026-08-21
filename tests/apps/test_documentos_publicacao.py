"""Emissão de documento com banco — o ato de publicar.

O que estes testes garantem, e nenhuma tela garante:
  · publicação recusada devolve TODAS as violações de uma vez;
  · corrigido o cadastro, a mesma emissão prossegue sem refazer o documento;
  · versão publicada é imutável;
  · peça de responsabilidade técnica só é publicada por engenheiro.
"""

from decimal import Decimal

import pytest

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Project
from apps.ativos.services import (
    acrescentar_fonte_de_energia,
    criar_maquina,
    definir_ponto_de_bloqueio,
)
from apps.checklists.models import MachineType
from apps.clientes.enums import PersonRole
from apps.clientes.models import Person
from apps.clientes.services import criar_cliente
from apps.core.models import User
from apps.documentos.enums import DocumentStatus
from apps.documentos.models import Document, PublicationBlock
from apps.documentos.services import (
    PermissaoDePublicacao,
    PublicacaoBloqueada,
    criar_documento,
    montar,
    publicar,
    sincronizar_bloqueios,
)


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(legal_name="Papelão do Vale", tax_id="98765432000155", actor=engenheiro_a)


@pytest.fixture
def responsavel(escopo_a, tenant_a):  # noqa: ANN001, ANN201
    return Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233344",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123456", professional_title="Engenheiro de Segurança do Trabalho",
    )


@pytest.fixture
def maquina(cliente, responsavel, tenant_a, engenheiro_a):  # noqa: ANN001, ANN201
    tipo = MachineType.objects.create(name="Prensa mecânica", nr12_annexes=["Anexo VIII"])
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number="CONV-1-001", art_number="SP20260814-0912",
        engineer=responsavel, status="active",
    )
    m = criar_maquina(
        client_id=cliente.pk, name="02 - Prensa excêntrica 60 t",
        actor=engenheiro_a, project=projeto, machine_type=tipo,
    )
    acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("0.8"), unit="bar",
        actor=engenheiro_a,
    )
    return m


def test_publicacao_recusada_lista_todos_os_bloqueios(maquina, engenheiro_a) -> None:  # noqa: ANN001
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    with pytest.raises(PublicacaoBloqueada) as exc:
        publicar(documento=doc, actor=engenheiro_a)
    assert [v.regra for v in exc.value.violacoes] == ["D-01"]
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.BLOCKED
    assert doc.versions.count() == 0


def test_bloqueio_fica_gravado_e_e_resolvido_ao_corrigir(maquina, engenheiro_a) -> None:  # noqa: ANN001
    """O bloqueio é tela de trabalho: sai, corrige, volta — não é aviso passageiro."""
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    sincronizar_bloqueios(documento=doc, contexto=montar(documento=doc))
    assert doc.bloqueios_abertos.count() == 1

    definir_ponto_de_bloqueio(
        energy_source=maquina.energy_sources.first(), identifier="PN-01",
        location="Unidade de tratamento de ar", actor=engenheiro_a,
    )
    sincronizar_bloqueios(documento=doc, contexto=montar(documento=doc))
    assert doc.bloqueios_abertos.count() == 0
    assert PublicationBlock.objects.filter(document=doc, resolved_at__isnull=False).count() == 1
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.READY


def test_publicacao_gera_versao_com_hash_e_trilha(maquina, engenheiro_a) -> None:  # noqa: ANN001
    definir_ponto_de_bloqueio(
        energy_source=maquina.energy_sources.first(), identifier="PN-01", actor=engenheiro_a
    )
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)

    doc.refresh_from_db()
    assert doc.status == DocumentStatus.PUBLISHED
    assert doc.current_version_id == versao.pk
    assert versao.number == 1
    assert len(versao.content_hash) == 64
    assert versao.signature_track == "a3_nuvem"
    assert versao.signature_status == "pending"
    assert versao.method_versions["hrn"] == "2.1"


def test_versao_publicada_e_imutavel(maquina, engenheiro_a) -> None:  # noqa: ANN001
    definir_ponto_de_bloqueio(
        energy_source=maquina.energy_sources.first(), identifier="PN-01", actor=engenheiro_a
    )
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)

    versao.content_hash = "0" * 64
    with pytest.raises(RuntimeError):
        versao.save()

    # a composição do PDF é a única atualização admitida
    versao.page_count = 12
    versao.save(update_fields=["page_count"])


def test_nova_publicacao_cria_segunda_versao(maquina, engenheiro_a) -> None:  # noqa: ANN001
    definir_ponto_de_bloqueio(
        energy_source=maquina.energy_sources.first(), identifier="PN-01", actor=engenheiro_a
    )
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    publicar(documento=doc, actor=engenheiro_a)
    segunda = publicar(documento=doc, actor=engenheiro_a)
    assert segunda.number == 2
    assert doc.versions.count() == 2


def test_analista_nao_publica_peca_de_responsabilidade(maquina, tenant_a, engenheiro_a) -> None:  # noqa: ANN001
    definir_ponto_de_bloqueio(
        energy_source=maquina.energy_sources.first(), identifier="PN-01", actor=engenheiro_a
    )
    analista = User.objects.create(
        username="ana@a.com", email="ana@a.com", tenant=tenant_a, role="analyst"
    )
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    with pytest.raises(PermissaoDePublicacao):
        publicar(documento=doc, actor=analista)
    assert doc.versions.count() == 0


def test_relatorio_de_conformidade_dispensa_engenheiro(maquina, tenant_a, engenheiro_a) -> None:  # noqa: ANN001
    """DOC03 é apuração assinada pela organização — analista publica (AD-11)."""
    analista = User.objects.create(
        username="ana2@a.com", email="ana2@a.com", tenant=tenant_a, role="analyst"
    )
    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=analista)
    assert versao.signature_track == "ecnpj_hsm"


def test_numero_do_documento_segue_projeto_e_template(maquina, engenheiro_a) -> None:  # noqa: ANN001
    doc = criar_documento(machine=maquina, template_code="DOC02", actor=engenheiro_a)
    assert doc.number == "CONV-1-001/DOC02-001"
    segundo = criar_documento(machine=maquina, template_code="DOC02", actor=engenheiro_a)
    assert segundo.number.endswith("-002")
    assert Document.objects.filter(machine=maquina).count() == 2
