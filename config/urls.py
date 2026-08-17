from django.contrib import admin
from django.urls import include, path

from apps.core.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz, name="healthz"),
    path("api/v1/", include("config.api_urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.ativos.urls")),
    path("", include("apps.clientes.urls")),
]
