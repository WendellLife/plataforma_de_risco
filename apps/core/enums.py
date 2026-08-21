from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Administrador"
    ENGINEER = "engineer", "Engenheiro"
    ANALYST = "analyst", "Analista"
    CLIENT_READER = "client_reader", "Cliente (leitura)"
    OPERATOR = "operator", "Operador"


# Somente engenheiro publica peça de responsabilidade técnica — nem administrador.
# Publicar exige registro no conselho, e registro é de pessoa física, não de cargo.
PERFIS_QUE_PUBLICAM = {UserRole.ENGINEER}
PERFIS_QUE_EXIGEM_MFA = {UserRole.ADMIN, UserRole.ENGINEER}

# Perfis que veem TODA a organização, sem carteira de clientes.
PERFIS_SEM_RESTRICAO_DE_CARTEIRA = {UserRole.ADMIN}

# Perfis cuja visibilidade é limitada aos clientes atribuídos a eles.
# Sem atribuição, o usuário não vê nada — e a tela diz isso em vez de parecer vazia.
PERFIS_COM_CARTEIRA = {UserRole.ENGINEER, UserRole.ANALYST, UserRole.OPERATOR, UserRole.CLIENT_READER}

# Perfis que apenas leem. Nenhuma tela de escrita é oferecida a eles.
PERFIS_SOMENTE_LEITURA = {UserRole.CLIENT_READER}


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
