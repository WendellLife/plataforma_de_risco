from django.contrib import admin

from .models import Component, EnergySource, LockoutPoint, Machine, Photo, Project


class EnergySourceInline(admin.TabularInline):
    model = EnergySource
    extra = 0
    fields = ("kind", "magnitude", "unit", "lockout_point", "notes")


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "org_unit", "serial_number", "machine_type", "status")
    list_filter = ("status", "client")
    search_fields = ("name", "serial_number", "asset_tag")
    inlines = [EnergySourceInline]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "art_number", "engineer", "status")
    list_filter = ("status",)


admin.site.register([LockoutPoint, Component, Photo])
