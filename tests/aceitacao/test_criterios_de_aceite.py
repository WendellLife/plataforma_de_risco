"""Critérios de aceite CA-01 a CA-10 — Espec 01, item 9.

Estes testes são a definição de PRONTO da plataforma, não testes de unidade. Cada um
verifica um critério de ponta a ponta, com dados reais, do jeito que a especificação
descreve — e não por inspeção de código.

Os dez passam. Onde um critério tem uma metade não verificável em suíte — desempenho sob
carga em CA-10, tempo de sincronização em 4G em CA-07 — o teste cobre o comportamento e a
lacuna está declarada no ACEITE.md, nunca disfarçada de verde.
"""

from __future__ import annotations

import uuid as uuid_lib
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Project
from apps.ativos.services import (
    acrescentar_fonte_de_energia,
    criar_maquina,
    definir_ponto_de_bloqueio,
)
from apps.campo.services import parear_aparelho, sincronizar
from apps.checklists.enums import ItemResult, Standard
from apps.checklists.models import LibraryItem, MachineType
from apps.checklists.services import abrir_aplicacao, encerrar_coleta, responder_item
from apps.clientes.enums import PersonRole
from apps.clientes.models import Person
from apps.clientes.services import criar_cliente
from apps.core.carteira import atribuir_cliente
from apps.core.tenancy import usando_tenant
from apps.core.enums import AuditAction
from apps.core.models import AuditLog, User
from apps.documentos.renderizacao import html_do_documento
from apps.documentos.services import (
    PermissaoDePublicacao,
    PublicacaoBloqueada,
    criar_documento,
    montar,
    publicar,
)
from apps.risco.enums import EstimateKind, Iso12100Step, Iso12100Type
from apps.risco.models import Hazard
from apps.risco.services import AnexoIncompativel, propor_medida, registrar_estimativa

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------- cenário base

@pytest.fixture
def analista(tenant_a):  # noqa: ANN001, ANN201
    return User.objects.create(
        username="ana@aceite.com", email="ana@aceite.com", tenant=tenant_a, role="analyst"
    )


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(legal_name="Metalúrgica Aceite", tax_id="12345678000199", actor=engenheiro_a)


@pytest.fixture
def maquina(cliente, tenant_a, engenheiro_a):  # noqa: ANN001, ANN201
    responsavel = Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233344",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123456", professional_title="Engenheiro de Segurança do Trabalho",
    )
    tipo = MachineType.objects.create(name="Prensa mecânica", nr12_annexes=["Anexo VIII"])
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number="ACE-1-001", art_number="SP20260819-0001",
        engineer=responsavel, status="active",
    )
    m = criar_maquina(
        client_id=cliente.pk, name="01 - Prensa excêntrica 60 t", actor=engenheiro_a,
        project=projeto, machine_type=tipo,
    )
    fonte = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("0.8"), unit="bar",
        actor=engenheiro_a,
    )
    definir_ponto_de_bloqueio(energy_source=fonte, identifier="PN-01", actor=engenheiro_a)
    return m


@pytest.fixture
def perigo(maquina, tenant_a, engenheiro_a):  # noqa: ANN001, ANN201
    p = Hazard.objects.create(
        tenant=tenant_a, machine=maquina, zone="Zona de prensagem",
        title="Esmagamento entre matriz e punção", iso12100_type=Iso12100Type.MECHANICAL,
    )
    registrar_estimativa(
        hazard=p, kind=EstimateKind.INITIAL, lo=Decimal("5"), fe=Decimal("2.5"),
        dph=Decimal("15"), np=Decimal("2"), actor=engenheiro_a,
    )
    propor_medida(
        hazard=p, iso12100_step=Iso12100Step.SAFEGUARDING,
        text="Instalar cortina de luz categoria 4 integrada ao comando bimanual.",
        actor=engenheiro_a,
    )
    return p


def _residual(perigo, engenheiro_a):  # noqa: ANN001, ANN202
    return registrar_estimativa(
        hazard=perigo, kind=EstimateKind.RESIDUAL, lo=Decimal("1"), fe=Decimal("2.5"),
        dph=Decimal("4"), np=Decimal("2"), actor=engenheiro_a,
    )


# ------------------------------------------------------------------------------- CA-01

def test_ca01_apreciacao_rastreavel(perigo, maquina, engenheiro_a) -> None:  # noqa: ANN001
    """Recusa a publicação até o residual ser recalculado; o laudo imprime as duas
    estimativas e a versão do método."""
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)

    with pytest.raises(PublicacaoBloqueada) as recusa:
        publicar(documento=doc, actor=engenheiro_a)
    assert "D-03" in [v.regra for v in recusa.value.violacoes]

    _residual(perigo, engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)
    assert versao.method_versions["hrn"] == "2.1"

    html = html_do_documento(documento=doc, contexto=montar(documento=doc))
    assert "375" in html          # HRN inicial
    assert "20" in html           # HRN residual
    assert "cortina de luz" in html.lower()      # a medida entre os dois
    assert "HRN versão 2.1" in html or "versão 2.1" in html


# ------------------------------------------------------------------------------- CA-02

def test_ca02_recomendacao_incompativel_nunca_alcanca_documento(
    perigo, maquina, engenheiro_a
) -> None:  # noqa: ANN001
    """Item de anexo incompatível é recusado na origem e o erro nomeia o anexo esperado."""
    item_de_outro_anexo = LibraryItem.objects.create(
        library_key="NR12-ANX-XI-001", standard=Standard.NR12, annex="Anexo XI",
        statement="Requisito de máquina de panificação.",
    )
    with pytest.raises(AnexoIncompativel) as erro:
        propor_medida(
            hazard=perigo, iso12100_step=Iso12100Step.SAFEGUARDING,
            text="Medida de outro anexo.", standard_reference=item_de_outro_anexo,
            actor=engenheiro_a,
        )
    assert "Anexo XI" in str(erro.value)
    assert "Anexo VIII" in str(erro.value)  # indica o anexo esperado

    _residual(perigo, engenheiro_a)
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    publicar(documento=doc, actor=engenheiro_a)
    assert "Anexo XI" not in html_do_documento(
        documento=doc, contexto=montar(documento=doc)
    )


# ------------------------------------------------------------------------------- CA-03

def test_ca03_loto_derivado_das_fontes_reais(cliente, tenant_a, engenheiro_a) -> None:  # noqa: ANN001
    """Uma etapa por fonte cadastrada; fonte sem ponto de bloqueio impede a emissão."""
    # Projeto com engenheiro e ART para que a única regra em jogo seja a D-01: sem ele,
    # a D-07 recusaria antes e o critério de aceite não chegaria a ser exercitado.
    responsavel = Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233355",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123457", professional_title="Engenheiro de Segurança do Trabalho",
    )
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number="ACE-3-001", art_number="SP20260819-0003",
        engineer=responsavel, status="active",
    )
    m = criar_maquina(
        client_id=cliente.pk, name="Serra fita", actor=engenheiro_a, project=projeto
    )
    eletrica = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.ELECTRIC, magnitude=Decimal("380"), unit="V",
        actor=engenheiro_a,
    )
    acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("6"), unit="bar",
        actor=engenheiro_a,
    )
    doc = criar_documento(machine=m, template_code="DOC02", actor=engenheiro_a)

    with pytest.raises(PublicacaoBloqueada) as recusa:
        publicar(documento=doc, actor=engenheiro_a)
    assert "D-01" in [v.regra for v in recusa.value.violacoes]

    definir_ponto_de_bloqueio(energy_source=eletrica, identifier="DJ-01", actor=engenheiro_a)
    for fonte in m.energy_sources.filter(lockout_point__isnull=True):
        definir_ponto_de_bloqueio(energy_source=fonte, identifier="PN-02", actor=engenheiro_a)

    contexto = montar(documento=doc)
    assert len(contexto.as_dict()["d"]["fontes"]) == 2  # uma etapa por fonte real
    assert not contexto.bloqueios


# ------------------------------------------------------------------------------- CA-04

def test_ca04_conformidade_comparavel_entre_maquinas(maquina, engenheiro_a) -> None:  # noqa: ANN001
    """Dois denominadores publicados juntos e N/A impresso com justificativa."""
    itens = [
        LibraryItem.objects.create(
            library_key=f"NR12-{n:03d}", standard=Standard.NR12,
            statement=f"Requisito {n}", display_order=n,
        )
        for n in (1, 2, 3, 4)
    ]
    aplicacao = abrir_aplicacao(
        machine_id=maquina.pk, standard=Standard.NR12, actor=engenheiro_a
    )
    responder_item(assessment=aplicacao, library_key=itens[0].library_key,
                   result=ItemResult.COMPLIANT, actor=engenheiro_a)
    responder_item(assessment=aplicacao, library_key=itens[1].library_key,
                   result=ItemResult.COMPLIANT, actor=engenheiro_a)
    responder_item(assessment=aplicacao, library_key=itens[2].library_key,
                   result=ItemResult.NON_COMPLIANT, actor=engenheiro_a)
    responder_item(
        assessment=aplicacao, library_key=itens[3].library_key,
        result=ItemResult.NOT_APPLICABLE,
        justification="Máquina não possui sistema hidráulico.", actor=engenheiro_a,
    )
    encerrar_coleta(assessment=aplicacao, actor=engenheiro_a)

    doc = criar_documento(machine=maquina, template_code="DOC03", actor=engenheiro_a)
    conformidade = montar(documento=doc).as_dict()["d"]["conformidade"]

    # base fixa 4 → 2/4 = 50%; avaliados 3 (o N/A sai do denominador) → 2/3 = 66,7%
    assert conformidade["base_fixa"] == 4
    assert conformidade["avaliados"] == 3
    assert conformidade["percentual_base_fixa"] != conformidade["percentual_avaliados"]

    html = html_do_documento(documento=doc, contexto=montar(documento=doc))
    assert "Máquina não possui sistema hidráulico." in html
    assert "base fixa" in html.lower()
    assert "avaliados" in html.lower()


# ------------------------------------------------------------------------------- CA-05

def test_ca05_publicacao_congelada(perigo, maquina, engenheiro_a) -> None:  # noqa: ANN001
    """Hash, versão de template e de método congelados; conteúdo em somente leitura."""
    _residual(perigo, engenheiro_a)
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)

    assert len(versao.content_hash) == 64
    assert versao.method_versions["hrn"] == "2.1"
    assert versao.signature_track  # assinatura acionada
    assert versao.signature_status == "pending"
    assert "rev." in versao.method_versions["template"]  # versão do template congelada
    congelado = versao.method_versions["template"]
    assert versao.context_snapshot  # o contexto inteiro virou conteúdo, não referência

    versao.context_snapshot = {"adulterado": True}
    with pytest.raises(RuntimeError):
        versao.save()

    versao.refresh_from_db()
    assert versao.method_versions["template"] == congelado
    assert "adulterado" not in versao.context_snapshot


# ------------------------------------------------------------------------------- CA-06

def test_ca06_verificabilidade_externa(perigo, maquina, engenheiro_a, client) -> None:  # noqa: ANN001
    """O QR abre a verificação pública sem login, confirmando hash, revisão e responsável."""
    _residual(perigo, engenheiro_a)
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    versao = publicar(documento=doc, actor=engenheiro_a)

    resposta = client.get(f"/api/v1/public/documents/{doc.public_uuid}")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["content_hash"] == versao.content_hash
    assert corpo["version"] == versao.number
    assert corpo["engineer"]


# ------------------------------------------------------------------------------- CA-07

def test_ca07_coleta_de_campo_sem_perda(maquina, analista, escopo_a) -> None:  # noqa: ANN001
    """Vistoria completa coletada offline sincroniza integralmente, com fila visível."""
    from apps.campo.selectors import lotes
    from apps.checklists.models import ItemResultRecord

    itens = [
        LibraryItem.objects.create(
            library_key=f"NR12-{n:03d}", standard=Standard.NR12,
            statement=f"Requisito {n}", display_order=n,
        )
        for n in range(1, 21)
    ]
    aplicacao = abrir_aplicacao(machine_id=maquina.pk, standard=Standard.NR12, actor=analista)
    aparelho, _ = parear_aparelho(
        operator=analista, label="Moto G84 Camila", device_id="moto-g84-camila"
    )

    registros = [
        {
            "type": "item_result", "client_uuid": str(uuid_lib.uuid4()),
            "assessment": str(aplicacao.public_uuid), "library_key": i.library_key,
            "result": ItemResult.COMPLIANT, "note": "Coletado em modo avião.",
        }
        for i in itens
    ]
    resultado = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=registros
    )

    assert resultado.applied == 20
    assert resultado.failed == 0
    assert not resultado.conflicts
    assert ItemResultRecord.objects.filter(assessment=aplicacao).count() == 20
    assert lotes().count() == 1  # fila visível na tela de sincronização


# ------------------------------------------------------------------------------- CA-08

def test_ca08_ciclo_fechado_entre_achado_e_correcao(
    perigo, maquina, engenheiro_a
) -> None:  # noqa: ANN001
    """Não conformidade gera ação com responsável e prazo; a evidência move a adequação."""
    from datetime import date

    from apps.planos.selectors import adequacao
    from apps.planos.services import (
        EncerramentoSemEvidencia,
        anexar_evidencia,
        concluir_acao,
        gerar_acoes_de_nao_conformidade,
    )

    acoes = gerar_acoes_de_nao_conformidade(machine=maquina, actor=engenheiro_a)
    assert acoes
    # Responsável nominal e prazo, nunca "a definir" nem data inventada.
    assert all(a.owner_id and a.deadline for a in acoes)
    assert all(a.suggested_days for a in acoes)  # prazo sugerido pela faixa de HRN

    antes = adequacao(machine=maquina).percentual
    assert antes == Decimal("0.0")

    alvo = acoes[0]
    # Sem prova não encerra — é a regra central do plano.
    with pytest.raises(EncerramentoSemEvidencia):
        concluir_acao(action=alvo, actor=engenheiro_a)

    anexar_evidencia(
        action=alvo, file_key="campo/1/protecao-instalada.jpg",
        caption="Proteção fixa com interbloqueio instalada",
        occurred_on=date(2026, 8, 10), actor=engenheiro_a,
    )
    concluir_acao(action=alvo, actor=engenheiro_a)

    depois = adequacao(machine=maquina)
    assert depois.percentual > antes
    alvo.refresh_from_db()
    assert alvo.completed_on == date(2026, 8, 10)  # data do FATO, não do lançamento


# ------------------------------------------------------------------------------- CA-09

def test_ca09_segregacao_de_responsabilidade(perigo, maquina, analista, engenheiro_a) -> None:  # noqa: ANN001
    """Analista não publica peça técnica por nenhum caminho, e a tentativa fica na trilha."""
    _residual(perigo, engenheiro_a)
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)

    with pytest.raises(PermissaoDePublicacao):
        publicar(documento=doc, actor=analista)
    assert doc.versions.count() == 0

    negado = AuditLog.objects.filter(
        action=AuditAction.PERMISSION_DENIED, actor=analista
    ).first()
    assert negado is not None
    assert negado.entity_table == doc._meta.db_table
    assert negado.new_value["motivo"]


def test_ca09_pela_interface_tambem(perigo, maquina, analista, engenheiro_a, client) -> None:  # noqa: ANN001
    """O mesmo bloqueio pela rota da interface — não existe caminho alternativo."""
    _residual(perigo, engenheiro_a)
    doc = criar_documento(machine=maquina, template_code="DOC01", actor=engenheiro_a)
    analista.set_password("senha-muito-longa-1")
    analista.save()
    # O cliente precisa estar na carteira do analista: sem isso o documento nem aparece
    # para ele (404 pela carteira) e a barreira de PERFIL — que é o que a CA-09 exige —
    # nunca chegaria a ser exercitada.
    atribuir_cliente(user=analista, client=maquina.client, actor=engenheiro_a)
    client.force_login(analista)

    resposta = client.post(reverse("publicar_documento", args=[doc.public_uuid]))
    assert resposta.status_code in (302, 403)
    # O middleware zera o contexto ao encerrar a requisição — correto em produção, onde
    # cada requisição é independente. Para conferir o banco, reentra-se no escopo.
    with usando_tenant(maquina.tenant_id):
        doc.refresh_from_db()
        assert doc.versions.count() == 0


# ------------------------------------------------------------------------------- CA-10

def test_ca10_geracao_em_lote(maquina, engenheiro_a, cliente) -> None:  # noqa: ANN001
    """Emissão em massa com triagem antes da fila e resultado por item.

    A metade de DESEMPENHO do critério (p95 abaixo de 800 ms sob carga) não é verificável
    aqui: exige ambiente com volume real. O que este teste garante é o comportamento —
    que o lote emite, tria, nomeia recusas e não vira transação única.
    """
    from apps.lotes.models import BatchStatus
    from apps.lotes.services import abrir_lote, executar_lote, planejar_lote
    from motores.lote import LIMITE_POR_LOTE

    plano = planejar_lote(template_code="DOC03", client=cliente, actor=engenheiro_a)
    assert plano.prontas, "a máquina do cenário base precisa estar elegível"
    # A estimativa de tempo do lote cheio precisa caber no critério de 30 minutos.
    assert plano.minutos_estimados <= 30
    assert LIMITE_POR_LOTE == 100

    lote = abrir_lote(
        template_code="DOC03", plano=plano, actor=engenheiro_a, client=cliente
    )
    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)
    lote.refresh_from_db()

    assert lote.status == BatchStatus.DONE
    assert lote.published_count == len(plano.prontas)
    assert lote.failed_count == 0
    assert lote.duracao_minutos is not None
    assert all(
        len(i.content_hash) == 64 for i in lote.items.filter(status="published")
    )
