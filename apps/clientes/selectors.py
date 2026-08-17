from __future__ import annotations

from django.db.models import Count, QuerySet

from .enums import ClientStatus, PersonRole
from .models import Client, OrgUnit, Person


def clientes(*, apenas_ativos: bool = True) -> QuerySet[Client]:
    qs = Client.objects.annotate(n_maquinas=Count("machines", distinct=True))
    if apenas_ativos:
        qs = qs.filter(status=ClientStatus.ACTIVE)
    return qs.order_by("legal_name")


def arvore_de_unidades(client: Client) -> QuerySet[OrgUnit]:
    return (
        OrgUnit.objects.filter(client=client)
        .select_related("parent")
        .order_by("kind", "name")
    )


def engenheiros() -> QuerySet[Person]:
    return Person.objects.filter(roles__contains=[PersonRole.ENGINEER]).order_by("name")
