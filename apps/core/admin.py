from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, ClientAssignment, Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "tax_id", "plan", "created_at")
    search_fields = ("legal_name", "tax_id")


class ClientAssignmentInline(admin.TabularInline):
    """Carteira do usuário. Vazia em perfil restrito significa NENHUM acesso."""

    model = ClientAssignment
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("client",)
    verbose_name = "cliente atribuído"
    verbose_name_plural = "carteira de clientes"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "role", "tenant", "escopo", "mfa_enabled", "is_active")
    list_filter = ("role", "tenant", "is_active")
    inlines = [ClientAssignmentInline]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Plataforma", {"fields": ("tenant", "role", "person", "mfa_enabled")}),
    )

    @admin.display(description="escopo de visibilidade")
    def escopo(self, obj: User) -> str:
        if obj.ve_toda_a_organizacao:
            return "toda a organização"
        quantos = obj.assignments.count()
        if quantos == 0:
            return "⚠ sem carteira — não vê nada"
        return f"{quantos} cliente(s)"


@admin.register(ClientAssignment)
class ClientAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "client", "created_at", "created_by")
    list_filter = ("tenant",)
    autocomplete_fields = ("user", "client")


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
