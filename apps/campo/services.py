"""Serviços de campo: pareamento e sincronização.

O contrato mais delicado do produto (Espec 08, item 6). Cinco invariantes que este
módulo existe para garantir:

1. **Idempotência em dois níveis.** O lote é identificado por client_batch_uuid e cada
   registro por client_uuid. Reenviar o mesmo lote devolve a resposta GRAVADA, sem
   reprocessar. Reenviar um registro dentro de outro lote é reconhecido como duplicado.
2. **Aceitação parcial.** Cada registro é aplicado em seu próprio savepoint. Um registro
   inválido nunca desfaz os válidos, e o motivo volta por registro.
3. **Conflito por acréscimo.** Coleta de campo NUNCA sobrescreve coleta feita na web.
   Divergência entra em conflict_report para revisão humana — não é erro do aparelho.
4. **Ordem irrelevante.** O aparelho envia em qualquer ordem; o servidor aplica na ordem
   de dependência (perigo, resposta, foto).
5. **Relógio do aparelho é dado, não verdade.** A data informada é preservada; a hora de
   recepção também é gravada; desvio acima de 15 minutos vira aviso no lote.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ativos.models import Machine
from apps.checklists.enums import ItemResult
from apps.checklists.models import Assessment, ItemResultRecord, LibraryItem
from apps.checklists.services import responder_item
from apps.core.enums import AuditAction, UserRole
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from apps.risco.models import Hazard
from motores.sincronizacao import (
    Conflito,
    Falha,
    ResultadoLote,
    conferir_relogio,
    ordenar_registros,
)
from motores.sincronizacao.relogio import SemFusoHorario

from .armazenamento import existe as foto_existe
from .enums import BatchStatus, DeviceStatus, PhotoSlot, RecordStatus, RecordType
from .models import Device, FieldPhoto, SyncBatch, SyncRecord

VALIDADE_TOKEN_DIAS = 30


class PareamentoRecusado(Exception):
    """Perfil sem direito a coleta de campo, ou aparelho revogado."""


# --------------------------------------------------------------------------- pareamento

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@transaction.atomic
def parear_aparelho(*, operator: User, label: str, device_id: str) -> tuple[Device, str]:
    """Emite o token do aparelho. O valor em claro é devolvido UMA vez e nunca gravado."""
    if operator.role not in (UserRole.ANALYST, UserRole.ENGINEER):
        raise PareamentoRecusado(
            "Somente analista ou engenheiro pareia aparelho de coleta de campo."
        )
    Device.objects.filter(
        operator=operator, device_id=device_id, status=DeviceStatus.ACTIVE
    ).update(status=DeviceStatus.REVOKED, revoked_at=timezone.now())

    token = secrets.token_urlsafe(32)
    aparelho = Device.objects.create(
        tenant_id=require_tenant(), label=label, device_id=device_id, operator=operator,
        token_hash=_hash_token(token),
        expires_at=timezone.now() + timedelta(days=VALIDADE_TOKEN_DIAS),
        created_by=operator,
    )
    registrar_auditoria(
        action=AuditAction.CREATE, entity=aparelho, actor=operator,
        new_value={"aparelho": label, "device_id": device_id, "validade_dias": VALIDADE_TOKEN_DIAS},
    )
    return aparelho, token


def aparelho_por_token(token: str) -> Device | None:
    """Resolve o token sem nunca comparar valor em claro no banco."""
    return (
        Device.sem_escopo.select_related("operator", "operator__tenant")
        .filter(token_hash=_hash_token(token), status=DeviceStatus.ACTIVE)
        .first()
    )


@transaction.atomic
def revogar_aparelho(*, aparelho: Device, actor: User | None = None) -> Device:
    aparelho.status = DeviceStatus.REVOKED
    aparelho.revoked_at = timezone.now()
    aparelho.save(update_fields=["status", "revoked_at", "updated_at"])
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=aparelho, actor=actor,
        new_value={"status": DeviceStatus.REVOKED},
    )
    return aparelho


# ------------------------------------------------------------------------ sincronização

def sincronizar(
    *, device: Device, client_batch_uuid: str, records: list[dict[str, Any]],
    device_reported_at=None,  # noqa: ANN001
) -> ResultadoLote:
    """Aplica um lote de coleta. Devolve o resultado no formato do contrato."""
    existente = SyncBatch.objects.filter(client_batch_uuid=client_batch_uuid).first()
    if existente is not None:
        # Reenvio: devolve a resposta gravada sem reprocessar nada.
        gravado = dict(existente.response or {})
        gravado["replayed"] = True
        resultado = ResultadoLote(client_batch_uuid=str(client_batch_uuid), replayed=True)
        resultado.applied = int(gravado.get("applied", 0))
        resultado.failures = [
            Falha(**{k: v for k, v in f.items() if k in ("client_uuid", "code", "message")})
            for f in gravado.get("failures", [])
        ]
        resultado.conflicts = [
            Conflito(
                client_uuid=c.get("client_uuid", ""), kind=c.get("kind", ""),
                message=c.get("message", ""), servidor=c.get("server_value", ""),
                aparelho=c.get("device_value", ""),
            )
            for c in gravado.get("conflict_report", [])
        ]
        resultado.warnings = list(gravado.get("warnings", []))
        return resultado

    resultado = ResultadoLote(client_batch_uuid=str(client_batch_uuid))
    agora = timezone.now()
    desvio = None
    if device_reported_at is not None:
        try:
            desvio = conferir_relogio(informado=device_reported_at, recebido=agora)
        except SemFusoHorario as erro:
            resultado.warnings.append(str(erro))
        else:
            if not desvio.tolerado:
                resultado.warnings.append(desvio.mensagem)

    with transaction.atomic():
        lote = SyncBatch.objects.create(
            tenant_id=require_tenant(), client_batch_uuid=client_batch_uuid, device=device,
            status=BatchStatus.EMPTY, device_reported_at=device_reported_at,
            clock_skew_seconds=desvio.segundos if desvio else None,
            created_by=device.operator,
        )

    for registro in ordenar_registros(records):
        _aplicar_com_savepoint(lote=lote, registro=registro, resultado=resultado)

    with transaction.atomic():
        lote.status = str(resultado.status)
        lote.applied_count = resultado.applied
        lote.failed_count = len(resultado.failures)
        lote.conflict_count = len(resultado.conflicts)
        lote.response = resultado.as_dict()
        lote.save(
            update_fields=[
                "status", "applied_count", "failed_count", "conflict_count",
                "response", "updated_at",
            ]
        )
        device.last_seen_at = agora
        device.save(update_fields=["last_seen_at", "updated_at"])
        registrar_auditoria(
            action=AuditAction.CREATE, entity=lote, actor=device.operator,
            new_value={
                "lote": str(client_batch_uuid), "status": str(resultado.status),
                "aplicados": resultado.applied, "falhas": len(resultado.failures),
                "conflitos": len(resultado.conflicts),
            },
        )
    return resultado


def _aplicar_com_savepoint(
    *, lote: SyncBatch, registro: dict[str, Any], resultado: ResultadoLote
) -> None:
    """Um savepoint por registro: registro inválido não desfaz os válidos."""
    client_uuid = str(registro.get("client_uuid", "") or "")
    tipo = str(registro.get("type", "") or "")

    if not client_uuid:
        resultado.failures.append(
            Falha(client_uuid="", code="validation_error", message="Registro sem client_uuid.")
        )
        return

    # Só registro APLICADO é duplicado. Falha e conflito precisam poder ser reenviados
    # depois de corrigidos — marcá-los como duplicados prenderia o dado no aparelho.
    ja_aplicado = (
        SyncRecord.objects.filter(client_uuid=client_uuid, status=RecordStatus.APPLIED)
        .exclude(batch=lote)
        .exists()
    )
    if ja_aplicado:
        _gravar_registro(lote, client_uuid, tipo, registro, RecordStatus.DUPLICATE)
        return  # não conta como aplicado nem como falha

    aplicador = {
        RecordType.ITEM_RESULT: _aplicar_item_result,
        RecordType.PHOTO: _aplicar_photo,
        RecordType.FIELD_HAZARD: _aplicar_field_hazard,
    }.get(tipo)

    if aplicador is None:
        resultado.failures.append(
            Falha(client_uuid=client_uuid, code="validation_error",
                  message=f"Tipo de registro desconhecido: {tipo or '(vazio)'}.")
        )
        _gravar_registro(lote, client_uuid, tipo, registro, RecordStatus.FAILED,
                         codigo="validation_error", mensagem="tipo desconhecido")
        return

    try:
        with transaction.atomic():
            entidade, conflito = aplicador(lote, registro)
            if conflito is not None:
                raise _Conflitou(conflito)
            _gravar_registro(
                lote, client_uuid, tipo, registro, RecordStatus.APPLIED, entidade=entidade
            )
        resultado.applied += 1
    except _Conflitou as parada:
        resultado.conflicts.append(parada.conflito)
        _gravar_registro(lote, client_uuid, tipo, registro, RecordStatus.CONFLICT,
                         codigo="sync_conflict", mensagem=parada.conflito.message)
    except (ValueError, LookupError) as erro:
        resultado.failures.append(
            Falha(client_uuid=client_uuid, code="validation_error", message=str(erro))
        )
        _gravar_registro(lote, client_uuid, tipo, registro, RecordStatus.FAILED,
                         codigo="validation_error", mensagem=str(erro))
    except IntegrityError as erro:
        resultado.failures.append(
            Falha(client_uuid=client_uuid, code="conflict",
                  message=f"Violação de restrição do banco: {erro}")
        )
        _gravar_registro(lote, client_uuid, tipo, registro, RecordStatus.FAILED,
                         codigo="conflict", mensagem=str(erro)[:200])


class _Conflitou(Exception):
    """Interno: desfaz o savepoint do registro e o classifica como conflito."""

    def __init__(self, conflito: Conflito) -> None:
        self.conflito = conflito
        super().__init__(conflito.message)


def _gravar_registro(
    lote: SyncBatch, client_uuid: str, tipo: str, payload: dict[str, Any], status: str,
    *, codigo: str = "", mensagem: str = "", entidade=None,  # noqa: ANN001
) -> SyncRecord:
    """client_uuid é único por tenant: a tentativa anterior (falha) dá lugar à nova."""
    with transaction.atomic():
        registro, _ = SyncRecord.objects.update_or_create(
            client_uuid=client_uuid,
            defaults={
                "tenant_id": require_tenant(), "batch": lote,
                "record_type": tipo if tipo in RecordType.values else RecordType.ITEM_RESULT,
                "payload": payload, "status": status, "failure_code": codigo,
                "failure_message": mensagem,
                "applied_table": entidade._meta.db_table if entidade is not None else "",
                "applied_id": entidade.pk if entidade is not None else None,
                "created_by": lote.device.operator,
            },
        )
        return registro


# ------------------------------------------------------------------- por tipo de registro

def _aplicar_item_result(lote: SyncBatch, r: dict[str, Any]):  # noqa: ANN202
    """Resposta de checklist. NUNCA sobrescreve resposta já dada na web."""
    aplicacao = _aplicacao(r.get("assessment"))
    chave = str(r.get("library_key", "") or "")
    if not chave:
        raise ValueError("library_key é obrigatório — item é identificado pela chave, não pela posição.")
    item = LibraryItem.objects.filter(standard=aplicacao.standard, library_key=chave).first()
    if item is None:
        raise LookupError(
            f"{chave} não existe na biblioteca de {aplicacao.get_standard_display()}."
        )
    resultado = str(r.get("result", "") or "")
    if resultado not in ItemResult.values:
        raise ValueError(f"Resultado inválido: {resultado or '(vazio)'}.")
    justificativa = str(r.get("justification", "") or "")
    if resultado == ItemResult.NOT_APPLICABLE and not justificativa.strip():
        raise ValueError("Item não aplicável exige justificativa (D-18).")

    ja_respondido = ItemResultRecord.objects.filter(
        assessment=aplicacao, library_item=item
    ).first()
    if ja_respondido is not None:
        if ja_respondido.result == resultado:
            return ja_respondido, None  # mesma resposta: acréscimo sem efeito
        return None, Conflito(
            client_uuid=str(r.get("client_uuid", "")),
            kind="checklist_item",
            message=(
                f"{chave} já foi respondido na web como "
                f"'{ja_respondido.get_result_display()}' e o aparelho trouxe outro resultado. "
                "A coleta de campo não sobrescreve — decida qual vale."
            ),
            servidor=ja_respondido.get_result_display(),
            aparelho=dict(ItemResult.choices).get(resultado, resultado),
        )

    return (
        responder_item(
            assessment=aplicacao, library_key=chave, result=resultado,
            justification=justificativa, note=str(r.get("note", "") or ""),
            actor=lote.device.operator,
        ),
        None,
    )


def _aplicar_photo(lote: SyncBatch, r: dict[str, Any]):  # noqa: ANN202
    """Registro da foto. O binário já subiu direto para o armazenamento."""
    chave = str(r.get("file_key", "") or "")
    if not chave:
        raise ValueError("file_key é obrigatório — peça a URL de envio em /field/photos/presign.")
    if not foto_existe(chave):
        raise LookupError(
            "O binário não está no armazenamento. Reenvie a foto para a URL assinada "
            "antes de confirmar o registro."
        )
    if FieldPhoto.objects.filter(file_key=chave).exists():
        return FieldPhoto.objects.get(file_key=chave), None

    slot = str(r.get("slot", PhotoSlot.FINDING) or PhotoSlot.FINDING)
    if slot not in PhotoSlot.values:
        raise ValueError(f"Slot de foto inválido: {slot}.")

    vinculo = r.get("link") or {}
    item_result = None
    perigo = None
    if vinculo:
        alvo = SyncRecord.objects.filter(
            client_uuid=str(vinculo.get("client_uuid", "") or ""),
            status=RecordStatus.APPLIED,
        ).first()
        if alvo is None:
            raise LookupError(
                "O registro que esta foto ilustra não foi aplicado. "
                "Reenvie os dois no mesmo lote."
            )
        if alvo.record_type == RecordType.ITEM_RESULT:
            item_result = ItemResultRecord.objects.filter(pk=alvo.applied_id).first()
        elif alvo.record_type == RecordType.FIELD_HAZARD:
            perigo = Hazard.objects.filter(pk=alvo.applied_id).first()

    maquina = _maquina(
        r.get("machine")
        or (item_result.assessment.machine.public_uuid if item_result else None)
        or (perigo.machine.public_uuid if perigo else None)
    )
    foto = FieldPhoto.objects.create(
        tenant_id=require_tenant(), machine=maquina, file_key=chave, slot=slot,
        caption=str(r.get("caption", "") or "")[:200], item_result=item_result, hazard=perigo,
        taken_at=r.get("taken_at") or None, geo=_geo(r.get("geo")),
        created_by=lote.device.operator,
    )
    return foto, None


def _aplicar_field_hazard(lote: SyncBatch, r: dict[str, Any]):  # noqa: ANN202
    """Perigo observado em campo. Zona precisa existir na máquina — não é texto livre."""
    maquina = _maquina(r.get("machine"))
    zona = str(r.get("zone", "") or "").strip()
    titulo = str(r.get("title", "") or "").strip()
    if not zona or not titulo:
        raise ValueError("Perigo de campo exige zona e título.")

    zonas = set(
        Hazard.objects.filter(machine=maquina).values_list("zone", flat=True)
    ) | set(maquina.components.values_list("kind", flat=True))
    if zonas and zona not in zonas:
        raise ValueError(
            f"zone não corresponde a nenhuma zona da máquina. Zonas conhecidas: "
            f"{', '.join(sorted(zonas))}."
        )

    tipo = str(r.get("iso12100_type", "mechanical") or "mechanical")
    perigo = Hazard.objects.create(
        tenant_id=require_tenant(), machine=maquina, zone=zona, title=titulo,
        description=str(r.get("description", "") or ""), iso12100_type=tipo,
        task=str(r.get("task", "") or "")[:160],
        existing_measures=str(r.get("existing_measures", "") or ""),
        created_by=lote.device.operator,
    )
    return perigo, None


def _aplicacao(uuid: Any) -> Assessment:
    aplicacao = Assessment.objects.filter(public_uuid=str(uuid or "")).first() if uuid else None
    if aplicacao is None:
        raise LookupError("A aplicação de checklist informada não existe neste tenant.")
    return aplicacao


def _maquina(uuid: Any) -> Machine:
    maquina = Machine.objects.filter(public_uuid=str(uuid or "")).first() if uuid else None
    if maquina is None:
        raise LookupError("A máquina informada não existe neste tenant.")
    return maquina


def _geo(valor: Any) -> dict[str, float]:
    if isinstance(valor, (list, tuple)) and len(valor) == 2:
        return {"lat": float(valor[0]), "lon": float(valor[1])}
    if isinstance(valor, dict) and "lat" in valor and "lon" in valor:
        return {"lat": float(valor["lat"]), "lon": float(valor["lon"])}
    return {}
