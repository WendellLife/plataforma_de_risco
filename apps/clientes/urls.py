from django.urls import path

from .views import lista_clientes

urlpatterns = [path("clientes/", lista_clientes, name="clientes")]
