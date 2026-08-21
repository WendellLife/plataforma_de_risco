from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import RegistroTenant

from .enums import (
    EnergyKind,
    MachineStatus,
    PhotoLinkKind,
    PhotoSlot,
    ProjectStatus,
    UNIDADES_POR_TIPO,
)


class Project(RegistroTenant):
    caminho_para_cliente = "client_id"

    """Agrupador contratual: ART, engenheiro responsável e analista."""

    client = models.ForeignKey("clientes.Client", on_delete=models.PROTECT, related_name="projects")
    number = models.CharField("número", max_length=40)
    name = models.CharField(max_length=200, blank=True)
    art_number = models.CharField("ART", max_length=40, blank=True)
    engineer = models.ForeignKey(
        "clientes.Person", null=True, blank=True, on_delete=models.PROTECT, related_name="projects_as_engineer"
    )
    analyst = models.ForeignKey(
        "clientes.Person", null=True, blank=True, on_delete=models.PROTECT, related_name="projects_as_analyst"
    )
    status = models.CharField(max_length=12, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)

    class Meta:
        verbose_name = "projeto"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ativos_project_numero_unico")
        ]
        indexes = [models.Index(fields=["tenant", "client", "status"])]

    def __str__(self) -> str:
        return f"{self.number} · {self.name or self.client.legal_name}"


class Machine(RegistroTenant):
    caminho_para_cliente = "client_id"

    client = models.ForeignKey("clientes.Client", on_delete=models.PROTECT, related_name="machines")
    org_unit = models.ForeignKey(
        "clientes.OrgUnit", null=True, blank=True, on_delete=models.PROTECT, related_name="machines"
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="machines"
    )
    machine_type = models.ForeignKey(
        "checklists.MachineType", null=True, blank=True, on_delete=models.PROTECT, related_name="machines"
    )
    name = models.CharField("identificação", max_length=200)
    serial_number = models.CharField("número de série", max_length=60, blank=True)
    asset_tag = models.CharField("patrimônio", max_length=60, blank=True)
    manufacturer = models.CharField("fabricante", max_length=120, blank=True)
    model = models.CharField("modelo", max_length=120, blank=True)
    year = models.PositiveSmallIntegerField("ano", null=True, blank=True)
    capacity = models.CharField("capacidade", max_length=80, blank=True)
    weight_kg = models.DecimalField("peso (kg)", max_digits=10, decimal_places=2, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    limits = models.JSONField("limites do equipamento", default=dict, blank=True)
    status = models.CharField(max_length=12, choices=MachineStatus.choices, default=MachineStatus.ACTIVE)

    class Meta:
        verbose_name = "máquina"
        indexes = [
            models.Index(fields=["tenant", "client", "status"]),
            models.Index(fields=["tenant", "serial_number"]),
            models.Index(fields=["tenant", "org_unit"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def fontes_sem_bloqueio(self) -> models.QuerySet[EnergySource]:
        """Fontes de energia que impedem a emissão de LOTO e do laudo (D-01)."""
        return self.energy_sources.filter(lockout_point__isnull=True)

    @property
    def pronta_para_loto(self) -> bool:
        return self.energy_sources.exists() and not self.fontes_sem_bloqueio.exists()


class LockoutPoint(RegistroTenant):
    caminho_para_cliente = "machine__client_id"

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="lockout_points")
    identifier = models.CharField("identificação física", max_length=40)
    location = models.CharField("localização", max_length=200, blank=True)
    device = models.CharField("dispositivo de bloqueio", max_length=120, blank=True)
    procedure_text = models.TextField("etapa de bloqueio e verificação", blank=True)
    photo = models.ForeignKey(
        "ativos.Photo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "ponto de bloqueio"
        verbose_name_plural = "pontos de bloqueio"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "machine", "identifier"], name="ativos_lockout_identificacao_unica"
            )
        ]

    def __str__(self) -> str:
        return f"{self.identifier} · {self.location}"


class EnergySource(RegistroTenant):
    caminho_para_cliente = "machine__client_id"

    """Fonte de energia TIPADA — nunca string livre (Espec 02, decisão estrutural)."""

    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="energy_sources")
    kind = models.CharField("tipo", max_length=16, choices=EnergyKind.choices)
    magnitude = models.DecimalField("magnitude", max_digits=10, decimal_places=3)
    unit = models.CharField("unidade", max_length=12)
    notes = models.CharField("observação", max_length=200, blank=True)
    lockout_point = models.OneToOneField(
        LockoutPoint, null=True, blank=True, on_delete=models.SET_NULL, related_name="energy_source"
    )

    class Meta:
        verbose_name = "fonte de energia"
        verbose_name_plural = "fontes de energia"
        constraints = [
            models.CheckConstraint(
                check=models.Q(magnitude__gt=0), name="ativos_energysource_magnitude_positiva"
            )
        ]
        indexes = [models.Index(fields=["tenant", "machine"]), models.Index(fields=["machine", "kind"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.magnitude:g} {self.unit}"

    def clean(self) -> None:
        esperadas = UNIDADES_POR_TIPO.get(self.kind, ())
        if esperadas and self.unit not in esperadas:
            raise ValidationError(
                {"unit": f"Unidade incompatível com fonte {self.get_kind_display()}. "
                         f"Esperado: {', '.join(esperadas)}."}
            )

    @property
    def rotulo(self) -> str:
        return str(self)


class Component(RegistroTenant):
    caminho_para_cliente = "machine__client_id"

    """Dispositivo de segurança instalado, com validade de certificado."""

    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="components")
    kind = models.CharField("dispositivo", max_length=80)
    manufacturer = models.CharField("fabricante", max_length=120, blank=True)
    model = models.CharField("modelo", max_length=120, blank=True)
    certificate_number = models.CharField("certificado", max_length=80, blank=True)
    certificate_valid_until = models.DateField("validade", null=True, blank=True)

    class Meta:
        verbose_name = "componente de segurança"
        verbose_name_plural = "componentes de segurança"
        indexes = [
            models.Index(fields=["tenant", "machine"]),
            models.Index(fields=["tenant", "certificate_valid_until"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind} · {self.manufacturer}".strip(" ·")


class Photo(RegistroTenant):
    # machine é opcional: foto sem máquina não pertence a cliente algum e some do filtro.
    caminho_para_cliente = "machine__client_id"

    machine = models.ForeignKey(
        Machine, null=True, blank=True, on_delete=models.CASCADE, related_name="photos"
    )
    slot = models.CharField(max_length=16, choices=PhotoSlot.choices, default=PhotoSlot.GENERAL)
    file_key = models.CharField(max_length=300)
    derivatives = models.JSONField(default=dict, blank=True)
    caption = models.CharField("legenda", max_length=300, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    link_kind = models.CharField(max_length=16, choices=PhotoLinkKind.choices, default=PhotoLinkKind.NONE)
    link_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "fotografia"
        verbose_name_plural = "fotografias"
        constraints = [
            models.CheckConstraint(
                check=models.Q(link_kind="none", link_id__isnull=True)
                | (~models.Q(link_kind="none") & models.Q(link_id__isnull=False)),
                name="ativos_photo_vinculo_coerente",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "machine", "slot"]),
            models.Index(fields=["tenant", "link_kind", "link_id"]),
        ]

    def __str__(self) -> str:
        return self.caption or self.file_key
