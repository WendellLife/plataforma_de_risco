from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import RegistroTenant
from motores.documento import TemplateDesconhecido
from motores.documento import template as template_do_catalogo

from .enums import DocumentStatus, RenderStatus, SignatureStatus


class Document(RegistroTenant):
    """Documento emitido para uma máquina a partir de um template do catálogo.

    O template NÃO é uma tabela: vive em motores/documento/catalogo.py. Aqui fica
    somente o código, para que a definição do documento seja versionada com o código
    e não editável por dado de cliente (Espec 03, item 1).
    """

    caminho_para_cliente = "machine__client_id"

    machine = models.ForeignKey("ativos.Machine", on_delete=models.PROTECT, related_name="documents")
    project = models.ForeignKey(
        "ativos.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="documents"
    )
    template_code = models.CharField("template", max_length=10)
    number = models.CharField("número do documento", max_length=60, blank=True)
    title = models.CharField("título", max_length=220)
    status = models.CharField(max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT)
    current_version = models.OneToOneField(
        "documentos.DocumentVersion", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        verbose_name = "documento"
        indexes = [
            models.Index(fields=["tenant", "machine", "template_code"]),
            models.Index(fields=["tenant", "status"]),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.template_code} · {self.machine.name}"

    def clean(self) -> None:
        try:
            template_do_catalogo(self.template_code)
        except TemplateDesconhecido as erro:
            raise ValidationError({"template_code": str(erro)}) from None

    @property
    def template(self):  # noqa: ANN201 - TemplateDoc do motor
        return template_do_catalogo(self.template_code)

    @property
    def proximo_numero_de_versao(self) -> int:
        return (self.versions.aggregate(n=models.Max("number"))["n"] or 0) + 1

    @property
    def bloqueios_abertos(self) -> models.QuerySet[PublicationBlock]:
        return self.blocks.filter(resolved_at__isnull=True, severity="block")


class DocumentVersion(RegistroTenant):
    """Versão publicada. Imutável: correção gera nova versão, nunca edição da anterior."""

    caminho_para_cliente = "document__machine__client_id"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveSmallIntegerField("versão")
    content_hash = models.CharField("hash do conteúdo", max_length=64)
    context_snapshot = models.JSONField("contexto congelado", default=dict, blank=True)
    verification_snapshot = models.JSONField("verificação no ato", default=list, blank=True)
    method_versions = models.JSONField("versões de método", default=dict, blank=True)
    pdf_key = models.CharField("chave no armazenamento", max_length=300, blank=True)
    pdf_sha256 = models.CharField("hash do binário", max_length=64, blank=True)
    pdf_bytes = models.PositiveIntegerField("tamanho do PDF", null=True, blank=True)
    page_count = models.PositiveSmallIntegerField("páginas", null=True, blank=True)
    render_status = models.CharField(max_length=10, choices=RenderStatus.choices, default=RenderStatus.PENDING)
    render_error = models.TextField(blank=True)
    signature_status = models.CharField(max_length=10, choices=SignatureStatus.choices, default=SignatureStatus.NONE)
    signature_track = models.CharField("trilha de assinatura", max_length=12, blank=True)
    signature = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField("publicado em")
    published_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "versão de documento"
        verbose_name_plural = "versões de documento"
        constraints = [
            models.UniqueConstraint(fields=["document", "number"], name="documentos_versao_unica")
        ]
        indexes = [models.Index(fields=["tenant", "-published_at"])]
        ordering = ("-number",)

    def __str__(self) -> str:
        return f"{self.document.template_code} v{self.number}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Versão publicada só admite atualização dos campos de composição e assinatura."""
        if self.pk is not None:
            permitido = {
                "render_status", "render_error", "pdf_key", "pdf_sha256", "pdf_bytes", "page_count",
                "signature_status", "signature", "signature_track", "updated_at", "updated_by",
            }
            campos = kwargs.get("update_fields")
            if campos is None or not set(campos).issubset(permitido):
                raise RuntimeError(
                    "Versão publicada é imutável — corrija emitindo uma nova versão."
                )
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def rotulo(self) -> str:
        return f"v{self.number} · {self.published_at:%d/%m/%Y %H:%M}"


class PublicationBlock(RegistroTenant):
    """Violação registrada na tentativa de publicação.

    Existe como TABELA porque o bloqueio é uma tela de trabalho, não um aviso passageiro:
    o usuário sai, corrige o cadastro e volta (Espec 04, item 5 — nunca toast).
    """

    caminho_para_cliente = "document__machine__client_id"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="blocks")
    rule = models.CharField("regra", max_length=10)
    severity = models.CharField("severidade", max_length=6)
    message = models.TextField("mensagem")
    entity = models.JSONField(default=dict, blank=True)
    fix_path = models.CharField("caminho de correção", max_length=300, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "bloqueio de publicação"
        verbose_name_plural = "bloqueios de publicação"
        indexes = [
            models.Index(fields=["tenant", "document", "resolved_at"]),
            models.Index(fields=["tenant", "rule"]),
        ]
        ordering = ("severity", "rule")

    def __str__(self) -> str:
        return f"{self.rule} · {self.message[:60]}"
