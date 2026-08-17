from __future__ import annotations

import uuid as uuid_lib

from django.contrib.auth.models import AbstractUser
from django.db import models

from .enums import AuditAction, Plan, UserRole
from .managers import SemEscopoManager, TenantManager


class UuidPublico(models.Model):
    """Identificador exposto em URL, QR e API. O id de banco nunca sai da aplicação."""

    public_uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class Registro(UuidPublico):
    """Colunas de infraestrutura comuns a toda tabela de negócio (Espec 07, item 1.1)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True


class RegistroTenant(Registro):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.PROTECT, related_name="+")

    objects = TenantManager()
    sem_escopo = SemEscopoManager()

    class Meta:
        abstract = True


class Tenant(Registro):
    legal_name = models.CharField("razão social", max_length=200)
    tax_id = models.CharField("CNPJ", max_length=14, unique=True)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.PILOT)
    enabled_modules = models.JSONField(default=list, blank=True)
    brand_logo_key = models.CharField(max_length=300, blank=True)
    default_locale = models.CharField(max_length=10, default="pt-BR")

    objects = SemEscopoManager()  # o próprio tenant não tem escopo de tenant

    class Meta:
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self) -> str:
        return self.legal_name


class User(AbstractUser):
    tenant = models.ForeignKey(
        Tenant, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    public_uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ANALYST)
    person = models.ForeignKey(
        "clientes.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    mfa_enabled = models.BooleanField("MFA habilitado", default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"],
                name="core_user_email_unico_por_tenant",
                condition=models.Q(email__gt=""),
            )
        ]
        indexes = [models.Index(fields=["tenant", "role"])]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def pode_publicar(self) -> bool:
        from .enums import PERFIS_QUE_PUBLICAM

        return self.role in PERFIS_QUE_PUBLICAM

    @property
    def exige_mfa(self) -> bool:
        from .enums import PERFIS_QUE_EXIGEM_MFA

        return self.role in PERFIS_QUE_EXIGEM_MFA


class AuditLog(models.Model):
    """Trilha imutável. Sem update e sem delete concedidos à aplicação."""

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="audit_logs")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=24, choices=AuditAction.choices)
    entity_table = models.CharField(max_length=64)
    entity_id = models.BigIntegerField(null=True, blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = SemEscopoManager()  # auditoria é lida com filtro explícito

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        indexes = [
            models.Index(fields=["tenant", "entity_table", "entity_id", "-occurred_at"]),
            models.Index(fields=["tenant", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.occurred_at:%d/%m/%Y %H:%M} · {self.action} · {self.entity_table}"

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk is not None:
            raise RuntimeError("Registro de auditoria é imutável.")
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def delete(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("Registro de auditoria não pode ser excluído.")
