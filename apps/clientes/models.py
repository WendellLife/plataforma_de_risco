from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import RegistroTenant

from .enums import ClientStatus, DocKind, OrgUnitKind, PAI_PERMITIDO


class Client(RegistroTenant):
    legal_name = models.CharField("razão social", max_length=200)
    tax_id = models.CharField("CNPJ", max_length=14)
    cnae = models.CharField("CNAE", max_length=10, blank=True)
    address = models.JSONField(default=dict, blank=True)
    contact = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=ClientStatus.choices, default=ClientStatus.ACTIVE)

    class Meta:
        verbose_name = "cliente"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "tax_id"], name="clientes_client_cnpj_unico")
        ]
        indexes = [models.Index(fields=["tenant", "legal_name"])]

    def __str__(self) -> str:
        return self.legal_name


class OrgUnit(RegistroTenant):
    """Unidade, setor, departamento e local — hierarquia física do cliente."""

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="org_units")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    kind = models.CharField(max_length=12, choices=OrgUnitKind.choices)
    name = models.CharField(max_length=160)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "unidade organizacional"
        verbose_name_plural = "unidades organizacionais"
        indexes = [
            models.Index(fields=["tenant", "client", "kind"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.name}"

    def clean(self) -> None:
        permitido = PAI_PERMITIDO.get(self.kind, set())
        if self.parent_id is None:
            if permitido:
                raise ValidationError({"parent": f"{self.get_kind_display()} exige unidade pai."})
            return
        if self.parent.kind not in permitido:
            raise ValidationError(
                {"parent": f"{self.get_kind_display()} não pode pertencer a {self.parent.get_kind_display()}."}
            )
        ancestral = self.parent
        while ancestral is not None:
            if ancestral.pk == self.pk:
                raise ValidationError({"parent": "Hierarquia circular não é permitida."})
            ancestral = ancestral.parent

    @property
    def caminho(self) -> str:
        partes, no = [self.name], self.parent
        while no is not None:
            partes.append(no.name)
            no = no.parent
        return " › ".join(reversed(partes))


class Person(RegistroTenant):
    """Pessoa com papéis acumuláveis. Engenheiro exige registro profissional."""

    name = models.CharField(max_length=200)
    doc_kind = models.CharField(max_length=6, choices=DocKind.choices, default=DocKind.CPF)
    doc_number = models.CharField(max_length=14)
    roles = models.JSONField(default=list, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    council = models.CharField("conselho", max_length=20, blank=True)
    council_state = models.CharField("UF do conselho", max_length=2, blank=True)
    council_number = models.CharField("registro", max_length=40, blank=True)
    professional_title = models.CharField("título profissional", max_length=120, blank=True)
    signature_image_key = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "pessoa"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "doc_kind", "doc_number"], name="clientes_person_doc_unico"
            )
        ]
        indexes = [models.Index(fields=["tenant", "name"])]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        from .enums import PersonRole

        if PersonRole.ENGINEER in (self.roles or []) and not self.council_number:
            raise ValidationError(
                {"council_number": "Engenheiro exige registro profissional (CREA/CAU)."}
            )

    @property
    def registro_completo(self) -> str:
        if not self.council_number:
            return ""
        return f"{self.council} {self.council_state} {self.council_number}".strip()
