from django.urls import path

from .views import painel

urlpatterns = [path("", painel, name="painel")]
