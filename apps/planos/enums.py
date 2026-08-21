from django.db import models


class ActionStatus(models.TextChoices):
    """Estado LANÇADO pelo usuário. A situação de prazo é derivada, não gravada."""

    OPEN = "open", "Aberta"
    IN_PROGRESS = "in_progress", "Em execução"
    DONE = "done", "Concluída"
    CANCELLED = "cancelled", "Cancelada"


class EvidenceKind(models.TextChoices):
    PHOTO = "photo", "Foto"
    INVOICE = "invoice", "Nota fiscal"
    CERTIFICATE = "certificate", "Certificado"
    REPORT = "report", "Laudo ou relatório"
    OTHER = "other", "Outro"


class ActionSource(models.TextChoices):
    """Origem da ação. Toda ação nasce de um achado — nunca do nada."""

    RECOMMENDATION = "recommendation", "Recomendação de apreciação"
    CHECKLIST = "checklist", "Item de checklist não conforme"
    FIELD = "field", "Observação de campo"
    MANUAL = "manual", "Lançamento manual"
