"""Emissão em lote com banco (CA-10).

O que estes testes protegem: o lote não é um atalho. Passa pelo mesmo verificador, pela
mesma exigência de engenheiro e produz as mesmas versões imutáveis da emissão individual.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.ativos.enums import EnergyKind
from apps.ativos.models import Machine, Project
from apps.ativos.services import (
    acrescentar_fonte_de_energia,
    criar_maquina,
    definir_ponto_de_bloqueio,
)
from apps.clientes.enums import PersonRole
from apps.clientes.models import Person
from apps.clientes.services import criar_cliente
from apps.core.enums import AuditAction
from apps.core.models import AuditLog, Tenant, User
from apps.documentos.enums import DocumentStatus
from apps.documentos.models import Document, DocumentVersion
from apps.documentos.services import PermissaoDePublicacao
from apps.lotes.models import BatchItemStatus, BatchStatus, IssueBatch
from apps.lotes.selectors import detalhe
from apps.lotes.services import (
    LoteVazio,
    abrir_lote,
    cancelar_lote,
    executar_lote,
    planejar_lote,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(
        legal_name="Parque Lote", tax_id="22222222000122", actor=engenheiro_a
    )


@pytest.fixture
def responsavel(tenant_a: Tenant, escopo_a) -> Person:  # noqa: ANN001
    return Person.objects.create(
        tenant=tenant_a, name="Wendell Engenheiro", doc_kind="cpf", doc_number="11122233344",
        roles=[PersonRole.ENGINEER], council="CREA", council_state="SP",
        council_number="5069123456", professional_title="Engenheiro de Segurança do Trabalho",
    )


def _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, nome: str) -> Machine:  # noqa: ANN001
    """Máquina completa: fonte de energia COM ponto de bloqueio — passa em D-01."""
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number=f"LT-{nome[:6]}",
        engineer=responsavel, status="active",
    )
    m = criar_maquina(
        client_id=cliente.pk, name=nome, actor=engenheiro_a, project=projeto
    )
    fonte = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.ELECTRIC, magnitude=Decimal("380"), unit="V",
        actor=engenheiro_a,
    )
    definir_ponto_de_bloqueio(energy_source=fonte, identifier="DJ-01", actor=engenheiro_a)
    return m


def _maquina_travada(cliente, tenant_a, responsavel, engenheiro_a, nome: str) -> Machine:  # noqa: ANN001
    """Fonte SEM ponto de bloqueio — trava em D-01, de propósito."""
    projeto = Project.objects.create(
        tenant=tenant_a, client=cliente, number=f"LT-{nome[:6]}",
        engineer=responsavel, status="active",
    )
    m = criar_maquina(
        client_id=cliente.pk, name=nome, actor=engenheiro_a, project=projeto
    )
    acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("6"), unit="bar",
        actor=engenheiro_a,
    )
    return m


# --------------------------------------------------------------------------- triagem

def test_triagem_separa_prontas_de_bloqueadas(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """A triagem roda ANTES da fila — é o que evita esperar meia hora por um lote ruim."""
    _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    _maquina_travada(cliente, tenant_a, responsavel, engenheiro_a, "02 Travada")

    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    assert len(plano.prontas) == 1
    assert len(plano.recusadas) == 1
    assert plano.recusadas[0].regras == ("D-01",)
    assert "bloqueio" in plano.recusadas[0].detalhe.lower()


def test_triagem_nao_publica_nada(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """Planejar é leitura: não pode deixar versão publicada como efeito colateral."""
    _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    assert DocumentVersion.objects.count() == 0


# ------------------------------------------------------------------------- abertura

def test_lote_sem_elegivel_e_recusado_com_motivo(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    _maquina_travada(cliente, tenant_a, responsavel, engenheiro_a, "02 Travada")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    with pytest.raises(LoteVazio, match="Nenhuma máquina elegível"):
        abrir_lote(
            template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
        )


def test_analista_nao_emite_em_lote_peca_tecnica(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """A regra de permissão NÃO afrouxa no lote — seria o furo mais fácil do produto."""
    analista = User.objects.create(
        username="ana@lote.com", email="ana@lote.com", tenant=tenant_a, role="analyst"
    )
    _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)

    with pytest.raises(PermissaoDePublicacao):
        abrir_lote(template_code="DOC02", plano=plano, actor=analista, client=cliente)
    assert IssueBatch.objects.count() == 0
    assert AuditLog.objects.filter(
        action=AuditAction.PERMISSION_DENIED, actor=analista
    ).exists()


def test_lote_guarda_o_plano_do_momento_do_pedido(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    _maquina_travada(cliente, tenant_a, responsavel, engenheiro_a, "02 Travada")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )
    assert lote.requested_count == 1
    assert lote.skipped_count == 1
    assert lote.plan_snapshot["ready"] == 1
    assert lote.items.count() == 2


# ------------------------------------------------------------------------- execução

def test_lote_publica_e_cada_versao_tem_hash_proprio(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    for n in range(3):
        _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, f"0{n + 1} Pronta")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )
    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)

    lote.refresh_from_db()
    assert lote.status == BatchStatus.DONE
    assert lote.published_count == 3
    assert lote.failed_count == 0
    hashes = set(
        lote.items.filter(status=BatchItemStatus.PUBLISHED).values_list("content_hash", flat=True)
    )
    assert len(hashes) == 3  # conteúdo distinto por máquina
    assert all(len(h) == 64 for h in hashes)
    assert Document.objects.filter(status=DocumentStatus.PUBLISHED).count() == 3


def test_falha_de_uma_nao_desfaz_as_outras(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    """O lote NÃO é transação única — versão publicada é imutável e permanece."""
    boas = [
        _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, f"0{n} Pronta")
        for n in (1, 2)
    ]
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )

    # Sabota a segunda máquina DEPOIS da triagem: simula cadastro mudando no meio.
    alvo = boas[1]
    alvo.energy_sources.all().delete()

    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)
    lote.refresh_from_db()
    assert lote.status == BatchStatus.PARTIAL
    assert lote.published_count == 1
    assert lote.failed_count == 1
    falho = lote.items.get(status=BatchItemStatus.FAILED)
    assert "D-01" in falho.rules
    assert falho.message


def test_bloqueio_surgido_apos_a_triagem_nomeia_a_regra(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    maquina = _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )
    maquina.energy_sources.all().delete()
    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)

    resultado = detalhe(IssueBatch.objects.get(pk=lote.pk))
    assert len(resultado["falhos"]) == 1
    assert resultado["progresso"].concluido


def test_lote_registra_duracao_para_o_criterio_de_30_minutos(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, "01 Pronta")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )
    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)
    lote.refresh_from_db()
    assert lote.started_at is not None
    assert lote.finished_at is not None
    assert lote.duracao_minutos is not None


# ----------------------------------------------------------------------- cancelamento

def test_cancelar_preserva_o_que_ja_saiu(
    cliente, tenant_a, responsavel, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    for n in (1, 2):
        _maquina_pronta(cliente, tenant_a, responsavel, engenheiro_a, f"0{n} Pronta")
    plano = planejar_lote(template_code="DOC02", client=cliente, actor=engenheiro_a)
    lote = abrir_lote(
        template_code="DOC02", plano=plano, actor=engenheiro_a, client=cliente
    )
    executar_lote(batch_id=lote.pk, actor_id=engenheiro_a.pk)
    lote.refresh_from_db()
    publicados = lote.published_count

    cancelar_lote(batch=lote, actor=engenheiro_a)
    lote.refresh_from_db()
    assert lote.status == BatchStatus.CANCELLED
    assert lote.published_count == publicados
    assert DocumentVersion.objects.count() == publicados
