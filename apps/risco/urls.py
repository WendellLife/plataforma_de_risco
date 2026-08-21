from django.urls import path

from .views import apreciacao, calculadora, previa_hrn, salvar_hrn

urlpatterns = [
    path("maquinas/<uuid:uuid>/riscos/", apreciacao, name="apreciacao"),
    path("riscos/<uuid:uuid>/estimativa/<str:kind>/", calculadora, name="calculadora_hrn"),
    path("riscos/<uuid:uuid>/estimativa/<str:kind>/previa", previa_hrn, name="previa_hrn"),
    path("riscos/<uuid:uuid>/estimativa/<str:kind>/salvar", salvar_hrn, name="salvar_hrn"),
]
