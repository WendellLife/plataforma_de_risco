from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "tax_id", "plan", "created_at")
    search_fields = ("legal_name", "tax_id")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "role", "tenant", "mfa_enabled", "is_active")
    list_filter = ("role", "tenant", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Plataforma", {"fields": ("tenant", "role", "person", "mfa_enabled")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "action", "entity_table", "entity_id", "actor")
    list_filter = ("action", "entity_table")
    readonly_fields = tuple(f.name for f in AuditLog._meta.fields)

    def has_add_permission(self, request, obj=None) -> bool:  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: ANN001
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: ANN001
        return False
