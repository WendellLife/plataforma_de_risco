"""Serviços do núcleo. Única casa da regra de negócio deste app."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .enums import AuditAction
from .models import AuditLog, Tenant, User
from .tenancy import require_tenant


def registrar_auditoria(
    *,
    action: AuditAction | str,
    entity: Any = None,
    entity_table: str = "",
    entity_id: int | None = None,
    actor: User | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip: str | None = None,
    tenant_id: int | None = None,
) -> AuditLog:
    """Grava uma linha na trilha. Chamado por todo serviço que escreve."""
    if entity is not None:
        entity_table = entity_table or entity._meta.db_table
        entity_id = entity_id or entity.pk
    return AuditLog.objects.create(
        tenant_id=tenant_id or require_tenant(),
        actor=actor,
        action=action,
        entity_table=entity_table,
        entity_id=entity_id,
        old_value=old_value or {},
        new_value=new_value or {},
        ip=ip,
    )


@transaction.atomic
def criar_usuario(
    *,
    tenant: Tenant,
    email: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    actor: User | None = None,
) -> User:
    """Cria usuário aplicando a exigência de MFA por perfil."""
    user = User(
        tenant=tenant,
        username=email,
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    user.mfa_enabled = user.exige_mfa
    user.set_unusable_password()
    user.full_clean(exclude=["password"])
    user.save()
    registrar_auditoria(
        action=AuditAction.CREATE,
        entity=user,
        actor=actor,
        new_value={"email": email, "role": role},
        tenant_id=tenant.pk,
    )
    return user
