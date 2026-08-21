from django.urls import path

from .views import cancelar, confirmar, detalhe_lote, lista_lotes, planejar

urlpatterns = [
    path("lotes/", lista_lotes, name="lotes"),
    path("lotes/planejar", planejar, name="planejar_lote"),
    path("lotes/confirmar", confirmar, name="confirmar_lote"),
    path("lotes/<uuid:uuid>/", detalhe_lote, name="lote"),
    path("lotes/<uuid:uuid>/cancelar", cancelar, name="cancelar_lote"),
]
