from django.contrib import admin

from .models import Assessment, ItemResultRecord, LibraryItem, MachineType


@admin.register(MachineType)
class MachineTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "nr12_annexes")


@admin.register(LibraryItem)
class LibraryItemAdmin(admin.ModelAdmin):
    list_display = ("library_key", "standard", "group_name", "display_order")
    list_filter = ("standard", "group_name")
    search_fields = ("library_key", "statement")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("machine", "standard", "status", "library_base_count", "closed_at")
    list_filter = ("standard", "status")


admin.site.register(ItemResultRecord)
