from __future__ import annotations

from django.db.models import QuerySet

from .models import LibraryItem


def biblioteca(*, standard: str, machine_type_id: int | None = None) -> QuerySet[LibraryItem]:
    qs = LibraryItem.objects.filter(standard=standard, retired_at__isnull=True)
    return qs.order_by("display_order")
