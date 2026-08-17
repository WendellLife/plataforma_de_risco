from __future__ import annotations

from rest_framework import mixins, viewsets

from .models import Client, Person
from .selectors import clientes
from .serializers import ClientSerializer, PersonSerializer


class ClientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ClientSerializer
    lookup_field = "public_uuid"

    def get_queryset(self):  # noqa: ANN201
        return clientes(apenas_ativos=self.request.query_params.get("status") != "all")


class PersonViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PersonSerializer
    lookup_field = "public_uuid"

    def get_queryset(self):  # noqa: ANN201
        qs = Person.objects.all()
        papel = self.request.query_params.get("role")
        return qs.filter(roles__contains=[papel]) if papel else qs
