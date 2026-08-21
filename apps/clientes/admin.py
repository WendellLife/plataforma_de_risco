from django.contrib import admin

from .models import Client, OrgUnit, Person


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "tax_id", "cnae", "status", "marca", "tenant")
    list_filter = ("status",)
    search_fields = ("legal_name", "tax_id")
    fieldsets = (
        (None, {"fields": ("tenant", "legal_name", "tax_id", "cnae", "address", "contact", "status")}),
        (
            "Identidade visual (white-label)",
            {
                "fields": (
                    "brand_display_name", "brand_logo_key", "brand_primary", "brand_secondary",
                ),
                "description": (
                    "Campo vazio usa a marca da plataforma. A cor entra na interface deste "
                    "cliente e o logo aparece na capa dos documentos dele — sempre ao lado "
                    "da identificação da consultoria emissora, nunca no lugar dela. "
                    "A página pública de verificação do QR não recebe marca de cliente: "
                    "ela prova autenticidade e precisa parecer o que é. "
                    "Cores em hexadecimal, com #."
                ),
            },
        ),
    )

    @admin.display(description="marca")
    def marca(self, obj: Client) -> str:
        return "própria" if obj.tem_marca_propria else "plataforma"


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "client", "parent")
    list_filter = ("kind",)
    search_fields = ("name",)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "doc_number", "council", "council_number")
    search_fields = ("name", "doc_number", "council_number")
