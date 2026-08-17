from __future__ import annotations

from django.db.models import QuerySet

from .models import AuditLog, User
from .tenancy import require_tenant


def usuarios_do_tenant() -> QuerySet[User]:
    return User.objects.filter(tenant_id=require_tenant()).order_by("first_name", "email")


def auditoria_recente(limite: int = 50) -> QuerySet[AuditLog]:
    return (
        AuditLog.objects.filter(tenant_id=require_tenant())
        .select_related("actor")
        .order_by("-occurred_at")[:limite]
    )
