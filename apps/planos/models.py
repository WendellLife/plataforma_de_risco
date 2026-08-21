from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import RegistroTenant

from .enums import ActionSource, ActionStatus, EvidenceKind


class ActionPlan(RegistroTenant):
    """Plano de ação de uma máquina. Agrupa as ações e dá um número ao conjunto."""

    caminho_para_cliente = "machine__client_id"

    machine = models.ForeignKey(
        "ativos.Machine", on_delete=models.CASCADE, related_name="action_plans"
    )
    number = models.CharField("número", max_length=40)
    title = models.CharField(max_length=200, blank=True)
    opened_at = models.DateField("aberto em", auto_now_add=True)

    class Meta:
        verbose_name = "plano de ação"
        verbose_name_plural = "planos de ação"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"], name="planos_actionplan_numero_unico_por_tenant"
            )
        ]
        indexes = [models.Index(fields=["tenant", "machine"])]

    def __str__(self) -> str:
        return f"{self.number} · {self.machine.name}"


class Action(RegistroTenant):
    """Ação corretiva.

    Três colunas que carregam decisão de domínio:

    - **owner é obrigatório.** Ação sem responsável nominal não é ação, é intenção.
    - **deadline** é sugerido pelo HRN da zona, mas gravado como decisão de quem responde.
    - **completed_on** é a data do FATO (quando a proteção foi instalada), separada de
      `created_at` (quando alguém digitou). É o que torna a curva de adequação auditável.

    Não existe coluna "atrasada": situação de prazo é derivada da data de hoje.
    """

    caminho_para_cliente = "plan__machine__client_id"

    plan = models.ForeignKey(ActionPlan, on_delete=models.CASCADE, related_name="actions")
    code = models.CharField("código", max_length=20)
    source = models.CharField(max_length=16, choices=ActionSource.choices)
    recommendation = models.ForeignKey(
        "risco.Recommendation", null=True, blank=True, on_delete=models.PROTECT,
        related_name="actions",
    )
    item_result = models.ForeignKey(
        "checklists.ItemResultRecord", null=True, blank=True, on_delete=models.PROTECT,
        related_name="actions",
    )
    hazard = models.ForeignKey(
        "risco.Hazard", null=True, blank=True, on_delete=models.PROTECT, related_name="actions"
    )
    text = models.TextField("o que fazer")
    owner = models.ForeignKey(
        "clientes.Person", on_delete=models.PROTECT, related_name="actions"
    )
    deadline = models.DateField("prazo")
    suggested_days = models.PositiveSmallIntegerField("prazo sugerido (dias)", null=True, blank=True)
    deadline_rationale = models.TextField("justificativa do prazo", blank=True)
    status = models.CharField(max_length=12, choices=ActionStatus.choices, default=ActionStatus.OPEN)
    completed_on = models.DateField("concluída em (data do fato)", null=True, blank=True)
    cancel_reason = models.TextField("motivo do cancelamento", blank=True)
    blocking = models.BooleanField("bloqueia publicação", default=False)
    estimated_cost = models.DecimalField(
        "custo estimado", max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "ação"
        verbose_name_plural = "ações"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"], name="planos_action_codigo_unico_por_tenant"
            ),
            # Uma recomendação gera UMA ação: sem isso o plano duplica a cada regeneração.
            models.UniqueConstraint(
                fields=["recommendation"], condition=models.Q(recommendation__isnull=False),
                name="planos_action_uma_por_recomendacao",
            ),
            models.UniqueConstraint(
                fields=["item_result"], condition=models.Q(item_result__isnull=False),
                name="planos_action_uma_por_item",
            ),
            # Concluída exige a data do fato; não concluída não pode ter data.
            models.CheckConstraint(
                check=(
                    models.Q(status="done", completed_on__isnull=False)
                    | (~models.Q(status="done") & models.Q(completed_on__isnull=True))
                ),
                name="planos_action_concluida_exige_data_do_fato",
            ),
            models.CheckConstraint(
                check=~models.Q(status="cancelled") | ~models.Q(cancel_reason=""),
                name="planos_action_cancelamento_exige_motivo",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "plan", "status"]),
            models.Index(fields=["tenant", "deadline"]),
            models.Index(fields=["tenant", "owner", "status"]),
        ]
        ordering = ("deadline", "code")

    def __str__(self) -> str:
        return f"{self.code} · {self.text[:60]}"

    def clean(self) -> None:
        if self.source == ActionSource.RECOMMENDATION and self.recommendation_id is None:
            raise ValidationError("Ação de origem 'recomendação' exige a recomendação vinculada.")
        if self.source == ActionSource.CHECKLIST and self.item_result_id is None:
            raise ValidationError("Ação de origem 'checklist' exige o item não conforme vinculado.")

    @property
    def origem_legivel(self) -> str:
        if self.hazard_id and self.recommendation_id:
            return f"{self.hazard.zone} · medida proposta"
        if self.item_result_id:
            return f"Checklist {self.item_result.library_item.library_key}"
        return self.get_source_display()

    @property
    def tem_evidencia(self) -> bool:
        return self.evidences.exists()


class Evidence(RegistroTenant):
    """Evidência de fechamento. Sem ela a ação não encerra (regra do produto).

    O binário vive no armazenamento; aqui fica o registro com o hash — a mesma lógica
    do documento publicado: prova precisa ser conferível, não apenas anexada.
    """

    caminho_para_cliente = "action__plan__machine__client_id"

    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="evidences")
    kind = models.CharField(max_length=12, choices=EvidenceKind.choices)
    file_key = models.CharField("chave no armazenamento", max_length=300)
    sha256 = models.CharField("hash do arquivo", max_length=64, blank=True)
    caption = models.CharField("descrição", max_length=200, blank=True)
    occurred_on = models.DateField("data do fato", null=True, blank=True)
    bytes_size = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "evidência"
        verbose_name_plural = "evidências"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "file_key"], name="planos_evidence_chave_unica"
            )
        ]
        indexes = [models.Index(fields=["tenant", "action"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.caption or self.file_key}"


class DeadlineChange(RegistroTenant):
    """Histórico de repactuação de prazo.

    Existe porque prazo que muda sem deixar rastro transforma o plano em ficção: no fim
    do ano tudo aparece "no prazo" porque a data foi empurrada seis vezes.
    """

    caminho_para_cliente = "action__plan__machine__client_id"

    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="deadline_changes")
    previous = models.DateField("prazo anterior")
    current = models.DateField("novo prazo")
    reason = models.TextField("justificativa")

    class Meta:
        verbose_name = "repactuação de prazo"
        verbose_name_plural = "repactuações de prazo"
        indexes = [models.Index(fields=["tenant", "action"])]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.previous:%d/%m/%Y} → {self.current:%d/%m/%Y}"

    @property
    def dias_empurrados(self) -> int:
        return (self.current - self.previous).days
