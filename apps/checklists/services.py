from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AuditAction
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from motores.conformidade import Conformidade, Resposta, ResultadoItem, calcular

from .enums import AssessmentStatus, ItemResult
from .models import Assessment, ItemResultRecord, LibraryItem


def base_fixa(standard: str) -> int:
    return LibraryItem.objects.filter(standard=standard, retired_at__isnull=True).count()


@transaction.atomic
def abrir_aplicacao(*, machine_id: int, standard: str, actor: User | None = None) -> Assessment:
    aplicacao = Assessment(
        tenant_id=require_tenant(), machine_id=machine_id, standard=standard,
        library_base_count=base_fixa(standard), collected_by=actor, created_by=actor,
    )
    aplicacao.full_clean()
    aplicacao.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=aplicacao, actor=actor,
        new_value={"standard": standard, "base_fixa": aplicacao.library_base_count},
    )
    return aplicacao


@transaction.atomic
def responder_item(
    *, assessment: Assessment, library_key: str, result: str,
    justification: str = "", note: str = "", actor: User | None = None,
) -> ItemResultRecord:
    """Responde um item pela CHAVE DE BIBLIOTECA, nunca pela posição exibida."""
    if result == ItemResult.NOT_APPLICABLE and not justification.strip():
        raise ValueError("Item não aplicável exige justificativa (D-18).")

    item = LibraryItem.objects.get(standard=assessment.standard, library_key=library_key)
    registro, _ = ItemResultRecord.objects.update_or_create(
        assessment=assessment,
        library_item=item,
        defaults={
            "tenant_id": require_tenant(), "result": result,
            "justification": justification, "note": note, "updated_by": actor,
        },
    )
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=registro, actor=actor,
        new_value={"library_key": library_key, "result": result},
    )
    return registro


def conformidade(assessment: Assessment) -> Conformidade:
    """Delega ao motor puro — sempre os dois denominadores."""
    respostas = [
        Resposta(
            library_key=r.library_item.library_key,
            resultado=ResultadoItem(r.result),
            justificativa=r.justification,
        )
        for r in assessment.results.select_related("library_item")
    ]
    return calcular(respostas, assessment.library_base_count)


@transaction.atomic
def encerrar_coleta(*, assessment: Assessment, actor: User | None = None) -> Assessment:
    sem_resposta = assessment.library_base_count - assessment.results.count()
    if sem_resposta > 0:
        raise ValueError(f"{sem_resposta} item(ns) sem resposta — a coleta não pode ser encerrada.")
    assessment.status = AssessmentStatus.CLOSED
    assessment.closed_at = timezone.now()
    assessment.updated_by = actor
    assessment.save(update_fields=["status", "closed_at", "updated_by", "updated_at"])
    registrar_auditoria(action=AuditAction.UPDATE, entity=assessment, actor=actor,
                        new_value={"status": AssessmentStatus.CLOSED})
    return assessment
