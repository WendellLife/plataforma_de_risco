from django.contrib import admin

from .models import IssueBatch, IssueBatchItem


class IssueBatchItemInline(admin.TabularInline):
    model = IssueBatchItem
    extra = 0
    readonly_fields = ("machine", "status", "version_number", "content_hash", "message")


@admin.register(IssueBatch)
class IssueBatchAdmin(admin.ModelAdmin):
    list_display = ("number", "template_code", "status", "requested_count",
                    "published_count", "failed_count", "duracao_minutos")
    list_filter = ("status", "template_code")
    inlines = [IssueBatchItemInline]


@admin.register(IssueBatchItem)
class IssueBatchItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "machine", "status", "version_number")
    list_filter = ("status",)
