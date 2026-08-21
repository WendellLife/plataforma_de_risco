"""Sprint 8 — contrato de sincronização de campo.

Os cinco invariantes: idempotência por lote e por registro, aceitação parcial, conflito
por acréscimo, ordem irrelevante e relógio do aparelho como dado (não verdade).
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ativos.models import Machine
from apps.checklists.enums import ItemResult, Standard
from apps.checklists.models import Assessment, ItemResultRecord, LibraryItem
from apps.checklists.services import abrir_aplicacao, responder_item
from apps.clientes.models import Client
from apps.core.models import Tenant, User
from apps.campo.enums import BatchStatus, RecordStatus
from apps.campo.models import Device, SyncBatch, SyncRecord
from apps.campo.services import PareamentoRecusado, parear_aparelho, sincronizar

pytestmark = pytest.mark.django_db


@pytest.fixture
def analista(tenant_a: Tenant) -> User:
    return User.objects.create(
        username="camila@a.com", email="camila@a.com", tenant=tenant_a, role="analyst"
    )


@pytest.fixture
def maquina(tenant_a: Tenant, escopo_a: None) -> Machine:
    cliente = Client.objects.create(
        tenant=tenant_a, legal_name="Gráfica Teste", tax_id="55555555000155"
    )
    return Machine.objects.create(tenant=tenant_a, client=cliente, name="Impressora offset")


@pytest.fixture
def biblioteca(db) -> list[LibraryItem]:  # noqa: ANN001
    return [
        LibraryItem.objects.create(
            library_key=f"NR12-{n:03d}", standard=Standard.NR12,
            statement=f"Requisito {n}", display_order=n,
        )
        for n in (21, 22, 23)
    ]


@pytest.fixture
def aplicacao(maquina: Machine, biblioteca, analista: User, escopo_a: None) -> Assessment:  # noqa: ANN001
    return abrir_aplicacao(machine_id=maquina.pk, standard=Standard.NR12, actor=analista)


@pytest.fixture
def aparelho(analista: User, escopo_a: None) -> Device:
    dispositivo, _ = parear_aparelho(
        operator=analista, label="Moto G84 Camila", device_id="moto-g84-camila"
    )
    return dispositivo


def _resposta(aplicacao: Assessment, chave: str, resultado: str = "non_compliant") -> dict:
    return {
        "type": "item_result", "client_uuid": str(uuid_lib.uuid4()),
        "assessment": str(aplicacao.public_uuid), "library_key": chave,
        "result": resultado, "note": "Coletado em campo.",
    }


# --------------------------------------------------------------------------- pareamento

def test_pareamento_devolve_token_em_claro_uma_vez(analista: User, escopo_a: None) -> None:
    dispositivo, token = parear_aparelho(
        operator=analista, label="Moto G84", device_id="moto-g84"
    )
    assert token
    assert token not in dispositivo.token_hash
    assert len(dispositivo.token_hash) == 64
    assert dispositivo.valido


def test_repareamento_revoga_o_aparelho_anterior(analista: User, escopo_a: None) -> None:
    antigo, _ = parear_aparelho(operator=analista, label="Moto G84", device_id="moto-g84")
    parear_aparelho(operator=analista, label="Moto G84", device_id="moto-g84")
    antigo.refresh_from_db()
    assert antigo.status == "revoked"


def test_perfil_sem_direito_nao_pareia(tenant_a: Tenant, escopo_a: None) -> None:
    cliente_user = User.objects.create(
        username="cli@a.com", email="cli@a.com", tenant=tenant_a, role="client_reader"
    )
    with pytest.raises(PareamentoRecusado):
        parear_aparelho(operator=cliente_user, label="Tablet", device_id="tablet-1")


# ----------------------------------------------------------------------- idempotência

def test_reenviar_o_mesmo_lote_nao_reprocessa(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    lote_uuid = str(uuid_lib.uuid4())
    registros = [_resposta(aplicacao, "NR12-021")]
    primeiro = sincronizar(device=aparelho, client_batch_uuid=lote_uuid, records=registros)
    segundo = sincronizar(device=aparelho, client_batch_uuid=lote_uuid, records=registros)
    assert primeiro.applied == 1
    assert segundo.applied == 1
    assert segundo.replayed is True
    assert SyncBatch.objects.filter(client_batch_uuid=lote_uuid).count() == 1
    assert ItemResultRecord.objects.filter(assessment=aplicacao).count() == 1


def test_mesmo_registro_em_outro_lote_e_duplicado(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    registro = _resposta(aplicacao, "NR12-021")
    sincronizar(device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[registro])
    segundo = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[registro]
    )
    assert segundo.applied == 0
    assert segundo.failed == 0
    assert SyncRecord.objects.filter(
        client_uuid=registro["client_uuid"], status=RecordStatus.DUPLICATE
    ).exists()


# --------------------------------------------------------------------- aceitação parcial

def test_registro_invalido_nao_derruba_os_validos(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    registros = [
        _resposta(aplicacao, "NR12-021"),
        _resposta(aplicacao, "NAO-EXISTE"),
        _resposta(aplicacao, "NR12-022"),
    ]
    r = sincronizar(device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=registros)
    assert r.applied == 2
    assert r.failed == 1
    assert str(r.status) == BatchStatus.PARTIAL
    assert ItemResultRecord.objects.filter(assessment=aplicacao).count() == 2


def test_falha_carrega_motivo_por_registro(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    invalido = _resposta(aplicacao, "NR12-021", resultado="talvez")
    r = sincronizar(device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[invalido])
    assert r.failures[0].client_uuid == invalido["client_uuid"]
    assert "talvez" in r.failures[0].message


def test_na_sem_justificativa_e_recusado_tambem_no_campo(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    """D-18 vale igual na web e no aparelho — a regra é do domínio, não da tela."""
    registro = _resposta(aplicacao, "NR12-021", resultado=ItemResult.NOT_APPLICABLE)
    r = sincronizar(device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[registro])
    assert r.applied == 0
    assert "D-18" in r.failures[0].message


# ------------------------------------------------------------------ conflito por acréscimo

def test_campo_nao_sobrescreve_resposta_da_web(
    aparelho: Device, aplicacao: Assessment, analista: User, escopo_a: None
) -> None:
    responder_item(
        assessment=aplicacao, library_key="NR12-021", result=ItemResult.COMPLIANT, actor=analista
    )
    r = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()),
        records=[_resposta(aplicacao, "NR12-021", resultado="non_compliant")],
    )
    assert r.applied == 0
    assert r.failed == 0
    assert len(r.conflicts) == 1
    gravado = ItemResultRecord.objects.get(assessment=aplicacao)
    assert gravado.result == ItemResult.COMPLIANT  # a web permanece


def test_mesma_resposta_nao_gera_conflito(
    aparelho: Device, aplicacao: Assessment, analista: User, escopo_a: None
) -> None:
    responder_item(
        assessment=aplicacao, library_key="NR12-021", result="non_compliant", actor=analista
    )
    r = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()),
        records=[_resposta(aplicacao, "NR12-021", resultado="non_compliant")],
    )
    assert r.applied == 1
    assert not r.conflicts


def test_conflito_marca_o_lote_para_revisao_humana(
    aparelho: Device, aplicacao: Assessment, analista: User, escopo_a: None
) -> None:
    responder_item(
        assessment=aplicacao, library_key="NR12-021", result=ItemResult.COMPLIANT, actor=analista
    )
    lote_uuid = str(uuid_lib.uuid4())
    sincronizar(
        device=aparelho, client_batch_uuid=lote_uuid,
        records=[
            _resposta(aplicacao, "NR12-021", resultado="non_compliant"),
            _resposta(aplicacao, "NR12-022"),
        ],
    )
    lote = SyncBatch.objects.get(client_batch_uuid=lote_uuid)
    assert lote.precisa_revisao
    assert lote.status == BatchStatus.PARTIAL
    assert lote.conflict_count == 1


# ------------------------------------------------------------------- perigo e relógio

def test_perigo_de_campo_com_zona_desconhecida_falha(
    aparelho: Device, maquina: Machine, escopo_a: None
) -> None:
    from apps.risco.models import Hazard

    Hazard.objects.create(
        tenant_id=aparelho.tenant_id, machine=maquina, zone="Zona de corte",
        title="Existente", iso12100_type="mechanical",
    )
    r = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()),
        records=[{
            "type": "field_hazard", "client_uuid": str(uuid_lib.uuid4()),
            "machine": str(maquina.public_uuid), "zone": "Inventada",
            "title": "Ponto de agarramento sem proteção",
        }],
    )
    assert r.applied == 0
    assert "zone não corresponde" in r.failures[0].message


def test_relogio_muito_divergente_entra_como_aviso(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    lote_uuid = str(uuid_lib.uuid4())
    r = sincronizar(
        device=aparelho, client_batch_uuid=lote_uuid,
        records=[_resposta(aplicacao, "NR12-021")],
        device_reported_at=timezone.now() - timedelta(hours=3),
    )
    assert r.applied == 1  # o aviso não impede a aplicação
    assert any("Relógio do aparelho" in a for a in r.warnings)
    lote = SyncBatch.objects.get(client_batch_uuid=lote_uuid)
    assert lote.clock_skew_seconds is not None
    assert lote.device_reported_at is not None


def test_ordem_dos_registros_nao_importa_na_pratica(
    aparelho: Device, aplicacao: Assessment, maquina: Machine, escopo_a: None
) -> None:
    """Perigo enviado DEPOIS da resposta é aplicado antes, por dependência."""
    r = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()),
        records=[
            _resposta(aplicacao, "NR12-021"),
            {"type": "field_hazard", "client_uuid": str(uuid_lib.uuid4()),
             "machine": str(maquina.public_uuid), "zone": "Alimentação",
             "title": "Ponto de agarramento sem proteção"},
        ],
    )
    assert r.applied == 2


def test_registro_que_falhou_pode_ser_reenviado(
    aparelho: Device, aplicacao: Assessment, escopo_a: None
) -> None:
    """Falha é retentável: marcar como duplicado prenderia o dado no aparelho."""
    registro = _resposta(aplicacao, "NAO-EXISTE")
    primeiro = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[registro]
    )
    assert primeiro.failed == 1
    corrigido = {**registro, "library_key": "NR12-021"}
    segundo = sincronizar(
        device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[corrigido]
    )
    assert segundo.applied == 1
    assert SyncRecord.objects.get(client_uuid=registro["client_uuid"]).status == RecordStatus.APPLIED


def test_lote_vazio_nao_e_erro(aparelho: Device, escopo_a: None) -> None:
    r = sincronizar(device=aparelho, client_batch_uuid=str(uuid_lib.uuid4()), records=[])
    assert str(r.status) == BatchStatus.EMPTY
    assert r.failed == 0
