from django.urls import path

from .api_views import inspections, pair, photos_presign, sync, sync_state

urlpatterns = [
    path("field/pair", pair, name="api_field_pair"),
    path("field/inspections", inspections, name="api_field_inspections"),
    path("field/sync", sync, name="api_field_sync"),
    path("field/sync/<uuid:client_batch_uuid>", sync_state, name="api_field_sync_state"),
    path("field/photos/presign", photos_presign, name="api_field_photos_presign"),
]
