from django.db import models


class RecordType(models.TextChoices):
    ITEM_RESULT = "item_result", "Resposta de checklist"
    PHOTO = "photo", "Foto"
    FIELD_HAZARD = "field_hazard", "Perigo observado em campo"


class BatchStatus(models.TextChoices):
    APPLIED = "applied", "Aplicado"
    PARTIAL = "partial", "Parcial"
    REJECTED = "rejected", "Recusado"
    EMPTY = "empty", "Vazio"


class RecordStatus(models.TextChoices):
    APPLIED = "applied", "Aplicado"
    FAILED = "failed", "Falhou"
    CONFLICT = "conflict", "Em conflito"
    DUPLICATE = "duplicate", "Duplicado — já aplicado antes"


class PhotoSlot(models.TextChoices):
    OVERVIEW = "overview", "Visão geral"
    FINDING = "finding", "Constatação"
    NAMEPLATE = "nameplate", "Placa de identificação"
    DEVICE = "device", "Dispositivo de segurança"
    LOCKOUT = "lockout", "Ponto de bloqueio"


class DeviceStatus(models.TextChoices):
    ACTIVE = "active", "Ativo"
    REVOKED = "revoked", "Revogado"
    EXPIRED = "expired", "Expirado"
