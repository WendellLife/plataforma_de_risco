from django.contrib import admin

from .models import Device, FieldPhoto, SyncBatch, SyncRecord


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("label", "operator", "status", "expires_at", "last_seen_at")
    list_filter = ("status",)
    readonly_fields = ("token_hash", "paired_at")


@admin.register(SyncBatch)
class SyncBatchAdmin(admin.ModelAdmin):
    list_display = ("client_batch_uuid", "device", "status", "applied_count",
                    "failed_count", "conflict_count", "received_at")
    list_filter = ("status",)


@admin.register(SyncRecord)
class SyncRecordAdmin(admin.ModelAdmin):
    list_display = ("client_uuid", "record_type", "status", "failure_code")
    list_filter = ("record_type", "status")


@admin.register(FieldPhoto)
class FieldPhotoAdmin(admin.ModelAdmin):
    list_display = ("file_key", "machine", "slot", "taken_at")
    list_filter = ("slot",)
