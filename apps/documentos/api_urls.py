from django.urls import path

from .api_views import verificacao_publica

urlpatterns = [
    path(
        "public/documents/<uuid:public_uuid>",
        verificacao_publica,
        name="api_verificacao_publica",
    ),
]
