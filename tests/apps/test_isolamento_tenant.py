"""Teste OBRIGATÓRIO em todo app: nenhum caminho lê dado de outro tenant."""

import pytest

from apps.clientes.models import Client
from apps.core.models import Tenant
from apps.core.tenancy import TenantEscopoAusente, usando_tenant


@pytest.fixture
def clientes_nos_dois_tenants(tenant_a: Tenant, tenant_b: Tenant) -> None:
    # Cada registro nasce dentro do escopo do próprio tenant, como em produção: o
    # manager padrão recusa escrita sem tenant no contexto, e é isso que se testa aqui.
    with usando_tenant(tenant_a.pk):
        Client.objects.create(tenant=tenant_a, legal_name="Cliente do A", tax_id="33333333000133")
    with usando_tenant(tenant_b.pk):
        Client.objects.create(tenant=tenant_b, legal_name="Cliente do B", tax_id="44444444000144")


def test_consulta_so_ve_o_proprio_tenant(clientes_nos_dois_tenants, tenant_a: Tenant) -> None:  # noqa: ANN001
    with usando_tenant(tenant_a.pk):
        nomes = list(Client.objects.values_list("legal_name", flat=True))
    assert nomes == ["Cliente do A"]


def test_consulta_sem_tenant_falha_ruidosamente(clientes_nos_dois_tenants) -> None:  # noqa: ANN001
    """O oposto — devolver tudo em silêncio — é o que produz vazamento entre clientes."""
    with pytest.raises(TenantEscopoAusente):
        list(Client.objects.all())


def test_acesso_sem_escopo_e_deliberado(clientes_nos_dois_tenants) -> None:  # noqa: ANN001
    assert Client.sem_escopo.count() == 2
