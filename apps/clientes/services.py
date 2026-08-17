from __future__ import annotations

from django.db import transaction

from apps.core.enums import AuditAction
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant

from .models import Client, OrgUnit, Person


@transaction.atomic
def criar_cliente(
    *, legal_name: str, tax_id: str, cnae: str = "", address: dict | None = None,
    contact: dict | None = None, actor: User | None = None,
) -> Client:
    cliente = Client(
        tenant_id=require_tenant(),
        legal_name=legal_name,
        tax_id=tax_id,
        cnae=cnae,
        address=address or {},
        contact=contact or {},
        created_by=actor,
    )
    cliente.full_clean()
    cliente.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=cliente, actor=actor,
        new_value={"legal_name": legal_name, "tax_id": tax_id},
    )
    return cliente


@transaction.atomic
def criar_unidade(
    *, client: Client, kind: str, name: str, parent: OrgUnit | None = None,
    actor: User | None = None,
) -> OrgUnit:
    unidade = OrgUnit(
        tenant_id=require_tenant(), client=client, kind=kind, name=name,
        parent=parent, created_by=actor,
    )
    unidade.full_clean()
    unidade.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=unidade, actor=actor,
        new_value={"kind": kind, "name": name, "parent": parent.pk if parent else None},
    )
    return unidade


@transaction.atomic
def criar_pessoa(*, name: str, doc_number: str, roles: list[str], actor: User | None = None,
                 **campos: object) -> Person:
    pessoa = Person(
        tenant_id=require_tenant(), name=name, doc_number=doc_number,
        roles=roles, created_by=actor, **campos,  # type: ignore[arg-type]
    )
    pessoa.full_clean()
    pessoa.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=pessoa, actor=actor,
        new_value={"name": name, "roles": roles},
    )
    return pessoa
