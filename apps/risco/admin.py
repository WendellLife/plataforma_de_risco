from django.contrib import admin

from .models import Hazard, HrnEstimate, Recommendation, SafetyCategory


class HrnEstimateInline(admin.TabularInline):
    model = HrnEstimate
    extra = 0
    readonly_fields = ("product", "band", "method_version")


@admin.register(Hazard)
class HazardAdmin(admin.ModelAdmin):
    list_display = ("title", "zone", "machine", "iso12100_type", "lifecycle_phase")
    list_filter = ("iso12100_type", "lifecycle_phase")
    search_fields = ("title", "zone")
    inlines = [HrnEstimateInline]


admin.site.register([Recommendation, SafetyCategory])
