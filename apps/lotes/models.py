from __future__ import annotations

from django.db import models

from apps.core.models import RegistroTenant


class BatchStatus(models.TextChoices):
    PLANNED = "planned", "Planejado"
    RUNNING = "running", "Em execução"
    DONE = "done", "Concluído"
    PARTIAL = "partial", "Concluído com falhas"
    CANCELLED = "cancelled", "Cancelado"


class BatchItemStatus(models.TextChoices):
    QUEUED = "queued", "Na fila"
    PUBLISHED = "published", "Publicado"
    FAILED = "failed", "Falhou"
    SKIPPED = "skipped", "Não elegível"


class IssueBatch(RegistroTenant):
    """Um pedido de emissão em lote.

    Existe como REGISTRO, não só como tarefa de fila: quem pediu 100 documentos precisa
    poder fechar o navegador, voltar depois e ver o que saiu, o que falhou e por quê. Fila
    sem registro persistente transforma isso em fé.
    """

    # Lote sem cliente é do parque inteiro: só quem vê tudo enxerga esses.
    caminho_para_cliente = "client_id"

    number = models.CharField("número", max_length=40)
    template_code = models.CharField("template", max_length=10)
    client = models.ForeignKey(
        "clientes.Client", null=True, blank=True, on_delete=models.PROTECT,
        related_name="issue_batches",
    )
    status = models.CharField(max_length=10, choices=BatchStatus.choices, default=BatchStatus.PLANNED)
    requested_count = models.PositiveSmallIntegerField("solicitados", default=0)
    published_count = models.PositiveSmallIntegerField("publicados", default=0)
    failed_count = models.PositiveSmallIntegerField("falhos", default=0)
    skipped_count = models.PositiveSmallIntegerField("não elegíveis", default=0)
    plan_snapshot = models.JSONField("plano no momento do pedido", default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "lote de emissão"
        verbose_name_plural = "lotes de emissão"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"], name="lotes_issuebatch_numero_unico_por_tenant"
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["tenant", "status"]),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.number} · {self.template_code} · {self.get_status_display()}"

    @property
    def duracao_minutos(self) -> int | None:
        if not self.started_at or not self.finished_at:
            return None
        return max(1, round((self.finished_at - self.started_at).total_seconds() / 60))

    @property
    def percentual(self) -> int:
        if self.requested_count == 0:
            return 100
        return round(
            (self.published_count + self.failed_count) / self.requested_count * 100
        )


class IssueBatchItem(RegistroTenant):
    """Uma máquina dentro do lote.

    O item guarda o resultado individual: cada emissão é seu próprio ato verificado, com
    sua própria versão e seu próprio hash. Uma falha aqui não desfaz as demais.
    """

    caminho_para_cliente = "machine__client_id"

    batch = models.ForeignKey(IssueBatch, on_delete=models.CASCADE, related_name="items")
    machine = models.ForeignKey(
        "ativos.Machine", on_delete=models.PROTECT, related_name="batch_items"
    )
    document = models.ForeignKey(
        "documentos.Document", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="batch_items",
    )
    version_number = models.PositiveSmallIntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=10, choices=BatchItemStatus.choices, default=BatchItemStatus.QUEUED
    )
    rules = models.JSONField("regras que impediram", default=list, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        verbose_name = "item de lote"
        verbose_name_plural = "itens de lote"
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "machine"], name="lotes_issuebatchitem_maquina_unica_no_lote"
            )
        ]
        indexes = [models.Index(fields=["tenant", "batch", "status"])]
        ordering = ("machine__name",)

    def __str__(self) -> str:
        return f"{self.machine.name} · {self.get_status_display()}"
