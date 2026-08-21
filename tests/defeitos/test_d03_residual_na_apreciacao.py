"""D-03 — recomendação sem risco residual estimado.

O defeito legado: laudo com medida proposta e nenhuma demonstração de que a medida
reduziu o risco. A apreciação precisa acusar a pendência ANTES da emissão, na própria
linha do perigo, e não só no verificador do documento.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.ativos.models import Machine
from apps.clientes.models import Client
from apps.core.models import Tenant
from apps.risco.enums import EstimateKind, Iso12100Step, Iso12100Type
from apps.risco.models import Hazard
from apps.risco.selectors import apreciacao_da_maquina, linha_de_perigo
from apps.risco.services import propor_medida, registrar_estimativa, riscos_sem_residual

pytestmark = pytest.mark.django_db


@pytest.fixture
def perigo_com_medida(tenant_a: Tenant, escopo_a: None) -> Hazard:
    cliente = Client.objects.create(
        tenant=tenant_a, legal_name="Serraria Teste", tax_id="44444444000144"
    )
    maquina = Machine.objects.create(tenant=tenant_a, client=cliente, name="Serra circular")
    perigo = Hazard.objects.create(
        tenant=tenant_a, machine=maquina, zone="Zona de corte", title="Contato com disco",
        iso12100_type=Iso12100Type.MECHANICAL,
    )
    registrar_estimativa(
        hazard=perigo, kind=EstimateKind.INITIAL, lo=Decimal("5"), fe=Decimal("4"),
        dph=Decimal("4"), np=Decimal("1"),
    )
    propor_medida(
        hazard=perigo, iso12100_step=Iso12100Step.SAFEGUARDING,
        text="Instalar proteção fixa com interbloqueio no acesso ao disco.",
    )
    return perigo


def test_d03_medida_sem_residual_e_pendencia_na_linha(perigo_com_medida: Hazard, escopo_a: None) -> None:
    linha = linha_de_perigo(perigo_com_medida)
    assert linha["pendencia_d03"] is True
    assert linha["comparacao"] is None


def test_d03_pendencia_contada_no_resumo_da_maquina(perigo_com_medida: Hazard, escopo_a: None) -> None:
    resumo = apreciacao_da_maquina(perigo_com_medida.machine)
    assert resumo["pendencias_d03"] == 1


def test_d03_insumo_do_verificador_lista_o_perigo(perigo_com_medida: Hazard, escopo_a: None) -> None:
    pendentes = riscos_sem_residual(perigo_com_medida.machine_id)
    assert [h.pk for h in pendentes] == [perigo_com_medida.pk]


def test_d03_residual_estimado_encerra_a_pendencia(perigo_com_medida: Hazard, escopo_a: None) -> None:
    registrar_estimativa(
        hazard=perigo_com_medida, kind=EstimateKind.RESIDUAL, lo=Decimal("0.5"),
        fe=Decimal("4"), dph=Decimal("4"), np=Decimal("1"),
    )
    linha = linha_de_perigo(perigo_com_medida)
    assert linha["pendencia_d03"] is False
    assert linha["comparacao"].melhorou
    assert riscos_sem_residual(perigo_com_medida.machine_id) == []
