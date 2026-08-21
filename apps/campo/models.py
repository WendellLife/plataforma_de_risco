from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.core.models import RegistroTenant

from .enums import BatchStatus, DeviceStatus, PhotoSlot, RecordStatus, RecordType


class Device(RegistroTenant):
    """Aparelho pareado. O token vive HASHEADO — o valor em claro sai uma única vez.

    Sem `caminho_para_cliente` de propósito: o aparelho pertence ao operador e à
    organização, não a um cliente. Um técnico leva o mesmo telefone a várias plantas.
    """

    label = models.CharField("identificação do aparelho", max_length=120)
    device_id = models.CharField("id informado pelo aparelho", max_length=120)
    operator = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="devices"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=DeviceStatus.choices, default=DeviceStatus.ACTIVE)
    paired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("expira em")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "aparelho de campo"
        verbose_name_plural = "aparelhos de campo"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "device_id"],
                condition=models.Q(status="active"),
                name="campo_device_id_unico_por_tenant_ativo",
            )
        ]
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self) -> str:
        return f"{self.label} · {self.operator}"

    @property
    def valido(self) -> bool:
        return self.status == DeviceStatus.ACTIVE and self.expires_at > timezone.now()

    @property
    def dias_para_expirar(self) -> int:
        return max((self.expires_at - timezone.now()).days, 0)

    def renovar(self, dias: int = 30) -> None:
        self.expires_at = timezone.now() + timedelta(days=dias)
        self.save(update_fields=["expires_at", "updated_at"])


class SyncBatch(RegistroTenant):
    """Lote enviado pelo aparelho.

    Sem `caminho_para_cliente`: um lote pode conter coleta de clientes diferentes. O
    filtro por cliente acontece nos DADOS aplicados (respostas, perigos, fotos), que têm
    o caminho declarado — não no envelope de transporte.

    client_batch_uuid é a chave de idempotência: reenviar o mesmo lote NÃO reprocessa —
    devolve a resposta gravada. É o que torna seguro o reenvio em rede instável.
    """

    client_batch_uuid = models.UUIDField("uuid do lote no aparelho")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="batches")
    status = models.CharField(max_length=10, choices=BatchStatus.choices)
    received_at = models.DateTimeField("recebido em", auto_now_add=True)
    device_reported_at = models.DateTimeField("hora do aparelho", null=True, blank=True)
    clock_skew_seconds = models.IntegerField("desvio de relógio (s)", null=True, blank=True)
    applied_count = models.PositiveSmallIntegerField(default=0)
    failed_count = models.PositiveSmallIntegerField(default=0)
    conflict_count = models.PositiveSmallIntegerField(default=0)
    response = models.JSONField("resposta devolvida", default=dict, blank=True)

    class Meta:
        verbose_name = "lote de sincronização"
        verbose_name_plural = "lotes de sincronização"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "client_batch_uuid"], name="campo_syncbatch_uuid_unico_por_tenant"
            )
        ]
        indexes = [models.Index(fields=["tenant", "-received_at"]), models.Index(fields=["tenant", "status"])]
        ordering = ("-received_at",)

    def __str__(self) -> str:
        return f"{self.client_batch_uuid} · {self.get_status_display()}"

    @property
    def precisa_revisao(self) -> bool:
        return self.conflict_count > 0


class SyncRecord(RegistroTenant):
    """Registro individual do lote.

    client_uuid é único por tenant: o mesmo registro reenviado em outro lote é
    reconhecido como duplicado e não duplica dado.
    """

    batch = models.ForeignKey(SyncBatch, on_delete=models.CASCADE, related_name="records")
    client_uuid = models.UUIDField("uuid do registro no aparelho")
    record_type = models.CharField(max_length=16, choices=RecordType.choices)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=RecordStatus.choices)
    failure_code = models.CharField(max_length=40, blank=True)
    failure_message = models.TextField(blank=True)
    applied_table = models.CharField(max_length=64, blank=True)
    applied_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "registro de sincronização"
        verbose_name_plural = "registros de sincronização"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "client_uuid"], name="campo_syncrecord_uuid_unico_por_tenant"
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "batch", "status"]),
            models.Index(fields=["tenant", "status", "record_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_record_type_display()} · {self.get_status_display()}"


class FieldPhoto(RegistroTenant):
    """Foto de campo. O binário vai direto do aparelho ao bucket; aqui fica o registro."""

    caminho_para_cliente = "machine__client_id"

    machine = models.ForeignKey(
        "ativos.Machine", on_delete=models.CASCADE, related_name="field_photos"
    )
    record = models.OneToOneField(
        SyncRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="photo"
    )
    file_key = models.CharField("chave no armazenamento", max_length=300)
    slot = models.CharField(max_length=12, choices=PhotoSlot.choices, default=PhotoSlot.FINDING)
    caption = models.CharField("legenda", max_length=200, blank=True)
    item_result = models.ForeignKey(
        "checklists.ItemResultRecord", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="photos",
    )
    hazard = models.ForeignKey(
        "risco.Hazard", null=True, blank=True, on_delete=models.SET_NULL, related_name="photos"
    )
    taken_at = models.DateTimeField("registrada em", null=True, blank=True)
    geo = models.JSONField("coordenada", default=dict, blank=True)
    bytes_size = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "foto de campo"
        verbose_name_plural = "fotos de campo"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "file_key"], name="campo_fieldphoto_chave_unica")
        ]
        indexes = [models.Index(fields=["tenant", "machine", "slot"])]

    def __str__(self) -> str:
        return f"{self.get_slot_display()} · {self.caption or self.file_key}"
