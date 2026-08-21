from django.contrib import admin

from .models import Document, DocumentVersion, PublicationBlock


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "template_code", "machine", "status", "created_at")
    list_filter = ("template_code", "status")
    search_fields = ("number", "title", "machine__name")
    autocomplete_fields = ()
    readonly_fields = ("public_uuid", "created_at", "updated_at")


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("document", "number", "published_at", "render_status", "signature_status")
    list_filter = ("render_status", "signature_status", "signature_track")
    readonly_fields = tuple(
        f.name for f in DocumentVersion._meta.fields if f.name != "id"
    )

    def has_add_permission(self, request, obj=None) -> bool:  # noqa: ANN001
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: ANN001
        return False


@admin.register(PublicationBlock)
class PublicationBlockAdmin(admin.ModelAdmin):
    list_display = ("rule", "severity", "document", "detected_at", "resolved_at")
    list_filter = ("rule", "severity")
    search_fields = ("message",)
