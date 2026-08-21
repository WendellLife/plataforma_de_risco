"""Regressões da carga de dados de demonstração."""

import pytest
from django.core.management import call_command

from apps.core.models import Tenant
from apps.core.tenancy import usando_tenant
from apps.planos.models import Evidence

pytestmark = pytest.mark.django_db


def test_seed_demo_pode_ser_executado_duas_vezes() -> None:
    call_command("seed_demo", verbosity=0)
    call_command("seed_demo", verbosity=0)

    tenant = Tenant.objects.get(tax_id="12345678000199")
    with usando_tenant(tenant.pk):
        assert Evidence.objects.filter(
            file_key=f"planos/{tenant.pk}/nf-protecao-fixa.pdf"
        ).count() == 1
