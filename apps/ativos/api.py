from __future__ import annotations

from rest_framework import mixins, viewsets

from .selectors import maquinas
from .serializers import MachineSerializer


class MachineViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MachineSerializer
    lookup_field = "public_uuid"

    def get_queryset(self):  # noqa: ANN201
        p = self.request.query_params
        return maquinas(
            status=p.get("status", "active") or None,
            busca=p.get("q", ""),
        ).prefetch_related("energy_sources__lockout_point")
