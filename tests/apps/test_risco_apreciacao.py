from __future__ import annotations

from decimal import Decimal

import pytest

from apps.ativos.models import Machine
from apps.clientes.models import Client
from apps.core.models import Tenant, User
from apps.risco.enums import EstimateKind, Iso12100Type
from apps.risco.models import Hazard
from apps.risco.selectors import apreciacao_da_maquina, linha_de_perigo
from apps.risco.services import registrar_estimativa

pytestmark = pytest.mark.django_db


@pytest.fixture
def maquina(tenant_a: Tenant, escopo_a: None) -> Machine:
    cliente = Client.objects.create(
        tenant=tenant_a, legal_name="Metalúrgica Teste", tax_id="33333333000133"
    )
    return Machine.objects.create(tenant=tenant_a, client=cliente, name="Prensa 40t")


@pytest.fixture
def perigo(tenant_a: Tenant, maquina: Machine, escopo_a: None) -> Hazard:
    return Hazard.objects.create(
        tenant=tenant_a, machine=maquina, zone="Zona de prensagem",
        title="Esmagamento entre matriz e punção", iso12100_type=Iso12100Type.MECHANICAL,
    )


def _estimar(perigo: Hazard, kind: str, lo: str, fe: str, dph: str, np: str, ator: User | None = None):  # noqa: ANN202
    return registrar_estimativa(
        hazard=perigo, kind=kind, lo=Decimal(lo), fe=Decimal(fe), dph=Decimal(dph),
        np=Decimal(np), actor=ator,
    )


def test_servidor_calcula_produto_faixa_e_versao(perigo: Hazard, escopo_a: None) -> None:
    """O cliente envia fatores; produto, faixa e versão do método são do servidor."""
    e = _estimar(perigo, EstimateKind.INITIAL, "5", "2.5", "15", "2")
    assert e.product == Decimal("375.000")
    assert e.band == "very_high"
    assert e.method_version == "2.1"


def test_reestimar_atualiza_em_vez_de_duplicar(perigo: Hazard, escopo_a: None) -> None:
    _estimar(perigo, EstimateKind.INITIAL, "5", "2.5", "15", "2")
    _estimar(perigo, EstimateKind.INITIAL, "1", "1", "2", "1")
    assert perigo.estimates.filter(kind=EstimateKind.INITIAL).count() == 1
    assert perigo.estimates.get(kind=EstimateKind.INITIAL).product == Decimal("2.000")


def test_linha_traz_o_movimento_entre_inicial_e_residual(perigo: Hazard, escopo_a: None) -> None:
    _estimar(perigo, EstimateKind.INITIAL, "5", "2.5", "15", "2")
    _estimar(perigo, EstimateKind.RESIDUAL, "1", "1", "2", "2")
    linha = linha_de_perigo(perigo)
    assert linha["comparacao"] is not None
    assert linha["comparacao"].melhorou
    assert linha["comparacao"].residual_tolerabel
    assert not linha["pendencia_d03"]


def test_fatores_aparecem_como_descritor_nao_como_numero_solto(perigo: Hazard, escopo_a: None) -> None:
    _estimar(perigo, EstimateKind.INITIAL, "5", "2.5", "15", "2")
    siglas = {f["sigla"]: f["descritor"] for f in linha_de_perigo(perigo)["fatores_inicial"]}
    assert siglas["DPH"] == "Fatalidade"
    assert siglas["FE"] == "De hora em hora"


def test_indicadores_da_apreciacao(maquina: Machine, perigo: Hazard, escopo_a: None) -> None:
    _estimar(perigo, EstimateKind.INITIAL, "5", "2.5", "15", "2")
    resumo = apreciacao_da_maquina(maquina)
    assert resumo["total"] == 1
    assert resumo["sem_estimativa"] == 0
    assert resumo["intoleraveis_antes"] == 1
    assert resumo["intoleraveis_depois"] == 0


def test_fator_zero_e_recusado_pelo_motor(perigo: Hazard, escopo_a: None) -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        _estimar(perigo, EstimateKind.INITIAL, "0", "1", "1", "1")
