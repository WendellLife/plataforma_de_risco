from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Administrador"
    ENGINEER = "engineer", "Engenheiro"
    ANALYST = "analyst", "Analista"
    CLIENT_READER = "client_reader", "Cliente (leitura)"
    OPERATOR = "operator", "Operador"


PERFIS_QUE_PUBLICAM = {UserRole.ENGINEER}
PERFIS_QUE_EXIGEM_MFA = {UserRole.ADMIN, UserRole.ENGINEER}


class AuditAction(models.TextChoices):
    CREATE = "create", "Criação"
    UPDATE = "update", "Alteração"
    PUBLISH = "publish", "Publicação"
    SIGN = "sign", "Assinatura"
    DELETE_ATTEMPT = "delete_attempt", "Tentativa de exclusão"
    LOGIN = "login", "Acesso"
    PERMISSION_DENIED = "permission_denied", "Acesso negado"


class Plan(models.TextChoices):
    PILOT = "pilot", "Piloto"
    STANDARD = "standard", "Padrão"
    ENTERPRISE = "enterprise", "Corporativo"
