from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.enums import AuditAction
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant

from .models import EnergySource, LockoutPoint, Machine


class SerieDuplicada(Exception):
    """Número de série já existe no cliente.

    É AVISO, não bloqueio (defeito D-09): a duplicidade existe no acervo real e não
    pode travar a importação. O chamador confirma explicitamente para prosseguir.
    """

    def __init__(self, maquinas: list[Machine]) -> None:
        self.maquinas = maquinas
        super().__init__("Número de série já cadastrado neste cliente.")


@transaction.atomic
def criar_maquina(
    *, client_id: int, name: str, serial_number: str = "", confirmar_serie_duplicada: bool = False,
    actor: User | None = None, **campos: object,
) -> Machine:
    if serial_number and not confirmar_serie_duplicada:
        existentes = list(
            Machine.objects.filter(client_id=client_id, serial_number=serial_number)
        )
        if existentes:
            raise SerieDuplicada(existentes)

    maquina = Machine(
        tenant_id=require_tenant(), client_id=client_id, name=name,
        serial_number=serial_number, created_by=actor, **campos,  # type: ignore[arg-type]
    )
    maquina.full_clean()
    maquina.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=maquina, actor=actor,
        new_value={"name": name, "serial_number": serial_number},
    )
    return maquina


@transaction.atomic
def acrescentar_fonte_de_energia(
    *, machine: Machine, kind: str, magnitude: Decimal, unit: str,
    notes: str = "", actor: User | None = None,
) -> EnergySource:
    fonte = EnergySource(
        tenant_id=require_tenant(), machine=machine, kind=kind,
        magnitude=magnitude, unit=unit, notes=notes, created_by=actor,
    )
    fonte.full_clean()
    fonte.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=fonte, actor=actor,
        new_value={"kind": kind, "magnitude": str(magnitude), "unit": unit},
    )
    return fonte


@transaction.atomic
def definir_ponto_de_bloqueio(
    *, energy_source: EnergySource, identifier: str, location: str = "",
    device: str = "", procedure_text: str = "", actor: User | None = None,
) -> LockoutPoint:
    """Cria o ponto de bloqueio e o vincula à fonte — libera LOTO e laudo (D-01)."""
    ponto = LockoutPoint(
        tenant_id=require_tenant(), machine=energy_source.machine, identifier=identifier,
        location=location, device=device, procedure_text=procedure_text, created_by=actor,
    )
    ponto.full_clean()
    ponto.save()

    anterior = energy_source.lockout_point_id
    energy_source.lockout_point = ponto
    energy_source.updated_by = actor
    energy_source.save(update_fields=["lockout_point", "updated_by", "updated_at"])

    registrar_auditoria(
        action=AuditAction.UPDATE, entity=energy_source, actor=actor,
        old_value={"lockout_point": anterior}, new_value={"lockout_point": ponto.pk},
    )
    return ponto
