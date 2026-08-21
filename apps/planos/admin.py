from django.contrib import admin

from .models import Action, ActionPlan, DeadlineChange, Evidence


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0


@admin.register(ActionPlan)
class ActionPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "machine", "opened_at")


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("code", "text", "owner", "deadline", "status", "blocking", "completed_on")
    list_filter = ("status", "source", "blocking")
    search_fields = ("code", "text")
    inlines = [EvidenceInline]


@admin.register(DeadlineChange)
class DeadlineChangeAdmin(admin.ModelAdmin):
    list_display = ("action", "previous", "current", "dias_empurrados")
    readonly_fields = ("previous", "current", "reason")
