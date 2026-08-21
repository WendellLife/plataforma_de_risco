from django.db import models


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    BLOCKED = "blocked", "Bloqueado pelo verificador"
    READY = "ready", "Pronto para publicar"
    PUBLISHED = "published", "Publicado"
    SUPERSEDED = "superseded", "Substituído por revisão"
    VOID = "void", "Anulado"


# Publicar exige documento nesses estados. Publicado não republica: gera nova versão.
ESTADOS_PUBLICAVEIS = {DocumentStatus.DRAFT, DocumentStatus.BLOCKED, DocumentStatus.READY}


class RenderStatus(models.TextChoices):
    PENDING = "pending", "Aguardando composição"
    RENDERED = "rendered", "PDF composto"
    FAILED = "failed", "Falha na composição"


class SignatureStatus(models.TextChoices):
    NONE = "none", "Sem assinatura"
    PENDING = "pending", "Aguardando assinatura"
    SIGNED = "signed", "Assinado"
    FAILED = "failed", "Falha na assinatura"
