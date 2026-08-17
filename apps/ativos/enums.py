from django.db import models


class ProjectStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    ACTIVE = "active", "Ativo"
    CLOSED = "closed", "Encerrado"


class MachineStatus(models.TextChoices):
    ACTIVE = "active", "Ativa"
    INACTIVE = "inactive", "Inativa"
    ARCHIVED = "archived", "Arquivada"


class EnergyKind(models.TextChoices):
    ELECTRIC = "electric", "Elétrica"
    PNEUMATIC = "pneumatic", "Pneumática"
    HYDRAULIC = "hydraulic", "Hidráulica"
    THERMAL = "thermal", "Térmica"
    GRAVITATIONAL = "gravitational", "Gravitacional"
    CHEMICAL = "chemical", "Química"
    RESIDUAL = "residual", "Residual"


# Unidade esperada por tipo de fonte — valida o cadastro (defeito D-01/D-11)
UNIDADES_POR_TIPO: dict[str, tuple[str, ...]] = {
    EnergyKind.ELECTRIC: ("V", "kV", "A"),
    EnergyKind.PNEUMATIC: ("bar", "psi", "kPa"),
    EnergyKind.HYDRAULIC: ("bar", "psi", "MPa"),
    EnergyKind.THERMAL: ("°C", "K"),
    EnergyKind.GRAVITATIONAL: ("kg", "t", "m"),
    EnergyKind.CHEMICAL: ("L", "kg", "ppm"),
    EnergyKind.RESIDUAL: ("J", "bar", "V", "kg"),
}


class PhotoSlot(models.TextChoices):
    PLATE = "plate", "Placa de identificação"
    FRONT = "front", "Frontal"
    BACK = "back", "Traseira"
    LEFT = "left", "Lateral esquerda"
    RIGHT = "right", "Lateral direita"
    GENERAL = "general", "Geral"
    FINDING = "finding", "Constatação"


class PhotoLinkKind(models.TextChoices):
    CHECKLIST_ITEM = "checklist_item", "Item de checklist"
    HAZARD_ZONE = "hazard_zone", "Zona de perigo"
    ACTION = "action", "Ação de plano"
    MACHINE = "machine", "Máquina"
    NONE = "none", "Sem vínculo"
