from django.contrib import admin

from .models import Client, OrgUnit, Person


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "tax_id", "cnae", "status", "tenant")
    list_filter = ("status",)
    search_fields = ("legal_name", "tax_id")


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "client", "parent")
    list_filter = ("kind",)
    search_fields = ("name",)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "doc_number", "council", "council_number")
    search_fields = ("name", "doc_number", "council_number")
