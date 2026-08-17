from django.db import models


class Standard(models.TextChoices):
    NR12 = "nr12", "NR-12"
    NR10 = "nr10", "NR-10"
    NR17 = "nr17", "NR-17"
    CUSTOM = "custom", "Personalizado"


class ItemResult(models.TextChoices):
    COMPLIANT = "compliant", "Conforme"
    NON_COMPLIANT = "non_compliant", "Não conforme"
    PARTIAL = "partial", "Parcial"
    NOT_APPLICABLE = "not_applicable", "Não aplicável"


class AssessmentStatus(models.TextChoices):
    DRAFT = "draft", "Em coleta"
    COLLECTED = "collected", "Coletado"
    CLOSED = "closed", "Encerrado"


class LibraryScope(models.TextChoices):
    GLOBAL = "global", "Global"
    TENANT = "tenant", "Do cliente"
