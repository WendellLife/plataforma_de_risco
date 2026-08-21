from django.urls import path

from .views import detalhe_lote, lista_lotes

urlpatterns = [
    path("campo/", lista_lotes, name="campo"),
    path("campo/lotes/<uuid:uuid>/", detalhe_lote, name="lote_campo"),
]
