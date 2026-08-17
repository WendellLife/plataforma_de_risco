from django.db import models


class ClientStatus(models.TextChoices):
    ACTIVE = "active", "Ativo"
    ARCHIVED = "archived", "Arquivado"


class OrgUnitKind(models.TextChoices):
    UNIT = "unit", "Unidade"
    SECTOR = "sector", "Setor"
    DEPARTMENT = "department", "Departamento"
    PLACE = "place", "Local"


# Hierarquia permitida: unidade > setor > departamento > local
PAI_PERMITIDO: dict[str, set[str]] = {
    OrgUnitKind.UNIT: set(),
    OrgUnitKind.SECTOR: {OrgUnitKind.UNIT},
    OrgUnitKind.DEPARTMENT: {OrgUnitKind.SECTOR, OrgUnitKind.UNIT},
    OrgUnitKind.PLACE: {OrgUnitKind.SECTOR, OrgUnitKind.DEPARTMENT, OrgUnitKind.UNIT},
}


class DocKind(models.TextChoices):
    CPF = "cpf", "CPF"
    CNPJ = "cnpj", "CNPJ"


class PersonRole(models.TextChoices):
    CLIENT = "client", "Cliente"
    ENGINEER = "engineer", "Engenheiro"
    ANALYST = "analyst", "Analista"
    RESPONSIBLE = "responsible", "Responsável"
    OPERATOR = "operator", "Operador"
