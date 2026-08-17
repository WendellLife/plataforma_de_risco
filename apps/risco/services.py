from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.enums import AuditAction
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from motores.hrn import Fatores, estimar

from .enums import EstimateKind
from .models import Hazard, HrnEstimate, Recommendation


class AnexoIncompativel(Exception):
    """Item normativo de anexo que não se aplica ao tipo de máquina (defeito D-02)."""


@transaction.atomic
def registrar_estimativa(
    *, hazard: Hazard, kind: str, lo: Decimal, fe: Decimal, dph: Decimal, np: Decimal,
    actor: User | None = None,
) -> HrnEstimate:
    """O SERVIDOR calcula produto, faixa e versão do método — o cliente só envia fatores."""
    resultado = estimar(Fatores(lo=lo, fe=fe, dph=dph, np=np))
    estimativa, _ = HrnEstimate.objects.update_or_create(
        hazard=hazard,
        kind=kind,
        defaults={
            "tenant_id": require_tenant(), "lo": lo, "fe": fe, "dph": dph, "np": np,
            "product": resultado.produto, "band": resultado.band,
            "method_version": resultado.method_version, "updated_by": actor,
        },
    )
    registrar_auditoria(
        action=AuditAction.UPDATE if estimativa.pk else AuditAction.CREATE,
        entity=estimativa, actor=actor,
        new_value={"kind": kind, "product": str(resultado.produto), "band": resultado.band},
    )
    return estimativa


@transaction.atomic
def propor_medida(
    *, hazard: Hazard, iso12100_step: str, text: str, standard_reference=None,  # noqa: ANN001
    device: str = "", deadline_days: int | None = None, actor: User | None = None,
) -> Recommendation:
    """Recusa item normativo cujo anexo não se aplica ao tipo da máquina (D-02)."""
    if standard_reference is not None and standard_reference.annex:
        tipo = hazard.machine.machine_type
        if tipo is None:
            raise AnexoIncompativel(
                "A máquina não tem tipo definido — não é possível validar a aplicabilidade do anexo."
            )
        if not tipo.aceita_anexo(standard_reference.annex):
            raise AnexoIncompativel(
                f"O anexo {standard_reference.annex} não se aplica a {tipo.name}. "
                f"Anexos aplicáveis: {', '.join(tipo.nr12_annexes) or 'nenhum cadastrado'}."
            )

    medida = Recommendation(
        tenant_id=require_tenant(), hazard=hazard, iso12100_step=iso12100_step, text=text,
        standard_reference=standard_reference, device=device, deadline_days=deadline_days,
        created_by=actor,
    )
    medida.full_clean()
    medida.save()
    registrar_auditoria(action=AuditAction.CREATE, entity=medida, actor=actor,
                        new_value={"step": iso12100_step, "text": text[:120]})
    return medida


def riscos_sem_residual(machine_id: int) -> list[Hazard]:
    """Insumo da regra D-03 do verificador."""
    return [
        h
        for h in Hazard.objects.filter(machine_id=machine_id).prefetch_related(
            "recommendations", "estimates"
        )
        if h.tem_medida_sem_residual
    ]
