from django.urls import include, path

urlpatterns = [
    path("", include("apps.ativos.api_urls")),
    path("", include("apps.clientes.api_urls")),
    path("", include("apps.campo.api_urls")),
    path("", include("apps.documentos.api_urls")),
]
