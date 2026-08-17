from __future__ import annotations

from collections.abc import Iterator

import pytest

from apps.core.models import Tenant, User
from apps.core.tenancy import usando_tenant


@pytest.fixture
def tenant_a(db) -> Tenant:  # noqa: ANN001
    return Tenant.objects.create(legal_name="Consultoria A", tax_id="11111111000111")


@pytest.fixture
def tenant_b(db) -> Tenant:  # noqa: ANN001
    return Tenant.objects.create(legal_name="Consultoria B", tax_id="22222222000122")


@pytest.fixture
def engenheiro_a(tenant_a: Tenant) -> User:
    return User.objects.create(
        username="eng@a.com", email="eng@a.com", tenant=tenant_a, role="engineer", mfa_enabled=True
    )


@pytest.fixture
def escopo_a(tenant_a: Tenant) -> Iterator[None]:
    with usando_tenant(tenant_a.pk):
        yield
