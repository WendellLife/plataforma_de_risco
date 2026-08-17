from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet

from apps.clientes.models import Client

from .enums import MachineStatus
from .models import Machine


def maquinas(
    *, client: Client | None = None, org_unit_id: int | None = None,
    status: str | None = MachineStatus.ACTIVE, busca: str = "",
) -> QuerySet[Machine]:
    qs = (
        Machine.objects.select_related("client", "org_unit", "machine_type")
        .annotate(
            n_fontes=Count("energy_sources", distinct=True),
            n_fontes_sem_bloqueio=Count(
                "energy_sources", filter=Q(energy_sources__lockout_point__isnull=True), distinct=True
            ),
        )
        .order_by("name")
    )
    if client is not None:
        qs = qs.filter(client=client)
    if org_unit_id:
        qs = qs.filter(org_unit_id=org_unit_id)
    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(Q(name__icontains=busca) | Q(serial_number__icontains=busca))
    return qs


def indicadores_do_parque() -> dict[str, Any]:
    base = Machine.objects.filter(status=MachineStatus.ACTIVE)
    total = base.count()
    sem_bloqueio = (
        base.filter(energy_sources__lockout_point__isnull=True).distinct().count()
    )
    sem_tipo = base.filter(machine_type__isnull=True).count()
    return {
        "maquinas": total,
        "bloqueios": sem_bloqueio,
        "sem_tipo": sem_tipo,
        "prontas_para_loto": total - sem_bloqueio,
        "percentual_pronto": round((total - sem_bloqueio) / total * 100, 1) if total else 0.0,
    }


def publicacoes_bloqueadas() -> list[dict[str, Any]]:
    """Máquinas cuja emissão está bloqueada por regra do verificador.

    No Sprint 1 a única regra ativa é D-01 (fonte de energia sem ponto de bloqueio).
    """
    travadas = (
        Machine.objects.filter(
            status=MachineStatus.ACTIVE, energy_sources__lockout_point__isnull=True
        )
        .select_related("client")
        .annotate(
            n_fontes_sem_bloqueio=Count(
                "energy_sources", filter=Q(energy_sources__lockout_point__isnull=True), distinct=True
            )
        )
        .distinct()
        .order_by("name")
    )
    return [
        {
            "regra": "D-01",
            "maquina": m,
            "mensagem": (
                f"{m.n_fontes_sem_bloqueio} fonte(s) de energia sem ponto de bloqueio — "
                "o procedimento LOTO e o laudo técnico não podem ser emitidos."
            ),
            "caminho": f"/maquinas/{m.public_uuid}/energia",
        }
        for m in travadas
    ]
