from django.urls import path

from .views import ficha_maquina, lista_maquinas

urlpatterns = [
    path("maquinas/", lista_maquinas, name="maquinas"),
    path("maquinas/<uuid:uuid>/", ficha_maquina, name="ficha_maquina"),
]
