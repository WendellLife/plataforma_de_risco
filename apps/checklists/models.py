from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import Registro, RegistroTenant

from .enums import AssessmentStatus, ItemResult, LibraryScope, Standard


class MachineType(Registro):
    """Tipo de máquina e anexos da NR-12 aplicáveis.

    É o que permite recusar recomendação de anexo incompatível (defeito D-02).
    """

    name = models.CharField(max_length=120)
    nr12_annexes = models.JSONField("anexos aplicáveis", default=list, blank=True)
    scope = models.CharField(max_length=10, choices=LibraryScope.choices, default=LibraryScope.GLOBAL)
    tenant = models.ForeignKey(
        "core.Tenant", null=True, blank=True, on_delete=models.CASCADE, related_name="machine_types"
    )

    class Meta:
        verbose_name = "tipo de máquina"
        verbose_name_plural = "tipos de máquina"
        constraints = [
            models.UniqueConstraint(
                fields=["name"], condition=models.Q(scope="global"),
                name="checklists_machinetype_nome_global_unico",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def aceita_anexo(self, anexo: str) -> bool:
        return anexo in (self.nr12_annexes or [])


class LibraryItem(Registro):
    """Item de biblioteca normativa.

    library_key é IDENTIDADE e é imutável; display_order é apresentação (defeito D-18).
    """

    library_key = models.CharField("identificador", max_length=40)
    standard = models.CharField(max_length=10, choices=Standard.choices)
    group_name = models.CharField("agrupamento", max_length=80, blank=True)
    statement = models.TextField("enunciado")
    help_text = models.TextField("orientação", blank=True)
    annex = models.CharField("anexo", max_length=20, blank=True)
    requires_evidence = models.BooleanField("exige evidência", default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    version = models.PositiveSmallIntegerField(default=1)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "item de biblioteca"
        verbose_name_plural = "itens de biblioteca"
        constraints = [
            models.UniqueConstraint(
                fields=["standard", "library_key", "version"], name="checklists_libraryitem_chave_unica"
            )
        ]
        indexes = [models.Index(fields=["standard", "display_order"])]
        ordering = ("standard", "display_order")

    def __str__(self) -> str:
        return f"{self.library_key} · {self.statement[:60]}"

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            anterior = LibraryItem.objects.filter(pk=self.pk).values_list("library_key", flat=True).first()
            if anterior and anterior != self.library_key:
                raise ValidationError("library_key é imutável — crie uma nova versão do item.")
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class Assessment(RegistroTenant):
    """Aplicação de um checklist a uma máquina.

    library_base_count guarda o tamanho da base fixa NO MOMENTO da aplicação — é o
    denominador que torna duas máquinas comparáveis.
    """

    machine = models.ForeignKey("ativos.Machine", on_delete=models.CASCADE, related_name="assessments")
    standard = models.CharField(max_length=10, choices=Standard.choices)
    library_base_count = models.PositiveSmallIntegerField("base fixa")
    status = models.CharField(max_length=12, choices=AssessmentStatus.choices, default=AssessmentStatus.DRAFT)
    collected_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "aplicação de checklist"
        verbose_name_plural = "aplicações de checklist"
        indexes = [models.Index(fields=["tenant", "machine", "standard", "status"])]

    def __str__(self) -> str:
        return f"{self.get_standard_display()} · {self.machine.name}"


class ItemResultRecord(RegistroTenant):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="results")
    library_item = models.ForeignKey(LibraryItem, on_delete=models.PROTECT, related_name="results")
    result = models.CharField(max_length=16, choices=ItemResult.choices)
    justification = models.TextField("justificativa", blank=True)
    note = models.TextField("observação", blank=True)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checklists_itemresult"
        verbose_name = "resposta de item"
        verbose_name_plural = "respostas de item"
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "library_item"], name="checklists_itemresult_unico_por_item"
            ),
            # D-18: item não aplicável nunca desaparece — exige justificativa
            models.CheckConstraint(
                check=~models.Q(result="not_applicable") | ~models.Q(justification=""),
                name="checklists_itemresult_na_exige_justificativa",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "result"])]

    def __str__(self) -> str:
        return f"{self.library_item.library_key} · {self.get_result_display()}"
