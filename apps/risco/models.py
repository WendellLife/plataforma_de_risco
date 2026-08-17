from __future__ import annotations

from django.db import models

from apps.core.models import RegistroTenant

from .enums import (
    EstimateKind,
    HrnBand,
    Iso12100Step,
    Iso12100Type,
    LifecyclePhase,
    PlrValue,
    RecommendationKind,
    SafetyCategoryValue,
)


class Hazard(RegistroTenant):
    machine = models.ForeignKey("ativos.Machine", on_delete=models.CASCADE, related_name="hazards")
    zone = models.CharField("zona de perigo", max_length=120)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    iso12100_type = models.CharField(max_length=16, choices=Iso12100Type.choices)
    lifecycle_phase = models.CharField(
        max_length=16, choices=LifecyclePhase.choices, default=LifecyclePhase.OPERATION
    )
    task = models.CharField("tarefa", max_length=160, blank=True)
    existing_measures = models.TextField("medidas existentes", blank=True)

    class Meta:
        verbose_name = "perigo"
        indexes = [
            models.Index(fields=["tenant", "machine"]),
            models.Index(fields=["tenant", "iso12100_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.zone} · {self.title}"

    @property
    def rotulo(self) -> str:
        return str(self)

    @property
    def tem_medida_sem_residual(self) -> bool:
        """Condição do defeito D-03 — bloqueia a publicação."""
        return (
            self.recommendations.exists()
            and not self.estimates.filter(kind=EstimateKind.RESIDUAL).exists()
        )


class HrnEstimate(RegistroTenant):
    """Estimativa de risco. Inicial e residual são REGISTROS, não campos (Espec 02)."""

    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="estimates")
    kind = models.CharField(max_length=10, choices=EstimateKind.choices)
    lo = models.DecimalField("probabilidade (LO)", max_digits=5, decimal_places=3)
    fe = models.DecimalField("frequência (FE)", max_digits=5, decimal_places=3)
    dph = models.DecimalField("gravidade (DPH)", max_digits=5, decimal_places=3)
    np = models.DecimalField("pessoas expostas (NP)", max_digits=5, decimal_places=3)
    product = models.DecimalField("HRN", max_digits=12, decimal_places=3)
    band = models.CharField("faixa", max_length=16, choices=HrnBand.choices)
    method_version = models.CharField("versão do método", max_length=10)

    class Meta:
        verbose_name = "estimativa de risco"
        verbose_name_plural = "estimativas de risco"
        constraints = [
            models.UniqueConstraint(fields=["hazard", "kind"], name="risco_hrnestimate_unica_por_tipo"),
            models.CheckConstraint(
                check=models.Q(lo__gt=0) & models.Q(fe__gt=0) & models.Q(dph__gt=0) & models.Q(np__gt=0),
                name="risco_hrnestimate_fatores_positivos",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "band"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · HRN {self.product:g} · {self.get_band_display()}"


class SafetyCategory(RegistroTenant):
    """Categoria de segurança e PLr da função de proteção — por ZONA, não por máquina."""

    hazard = models.OneToOneField(Hazard, on_delete=models.CASCADE, related_name="safety_category")
    s = models.PositiveSmallIntegerField("gravidade (S)")
    f = models.PositiveSmallIntegerField("frequência (F)")
    p = models.PositiveSmallIntegerField("possibilidade de evitar (P)")
    category = models.CharField(max_length=2, choices=SafetyCategoryValue.choices)
    plr = models.CharField("PLr", max_length=2, choices=PlrValue.choices)
    rationale = models.TextField("justificativa", blank=True)

    class Meta:
        verbose_name = "categoria de segurança"
        verbose_name_plural = "categorias de segurança"

    def __str__(self) -> str:
        return f"Cat. {self.get_category_display()} · PLr {self.get_plr_display()}"


class Recommendation(RegistroTenant):
    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="recommendations")
    kind = models.CharField(max_length=12, choices=RecommendationKind.choices, default=RecommendationKind.NORMATIVE)
    standard_reference = models.ForeignKey(
        "checklists.LibraryItem", null=True, blank=True, on_delete=models.PROTECT, related_name="recommendations"
    )
    iso12100_step = models.CharField(max_length=20, choices=Iso12100Step.choices)
    text = models.TextField("medida proposta")
    device = models.CharField("dispositivo", max_length=120, blank=True)
    deadline_days = models.PositiveSmallIntegerField("prazo sugerido (dias)", null=True, blank=True)

    class Meta:
        verbose_name = "recomendação"
        verbose_name_plural = "recomendações"
        indexes = [models.Index(fields=["tenant", "hazard"])]

    def __str__(self) -> str:
        return self.text[:80]
