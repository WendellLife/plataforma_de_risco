from django.db import models


class Iso12100Type(models.TextChoices):
    MECHANICAL = "mechanical", "Mecânico"
    ELECTRICAL = "electrical", "Elétrico"
    THERMAL = "thermal", "Térmico"
    NOISE = "noise", "Ruído"
    VIBRATION = "vibration", "Vibração"
    RADIATION = "radiation", "Radiação"
    MATERIAL = "material", "Material ou substância"
    ERGONOMIC = "ergonomic", "Ergonômico"
    ENVIRONMENT = "environment", "Ambiente de trabalho"
    COMBINATION = "combination", "Combinação de perigos"


class Iso12100Step(models.TextChoices):
    INHERENT_DESIGN = "inherent_design", "Projeto intrinsecamente seguro"
    SAFEGUARDING = "safeguarding", "Proteção e medidas complementares"
    INFORMATION = "information", "Informação de uso"


class LifecyclePhase(models.TextChoices):
    OPERATION = "operation", "Operação"
    SETUP = "setup", "Preparação"
    MAINTENANCE = "maintenance", "Manutenção"
    CLEANING = "cleaning", "Limpeza"
    TRANSPORT = "transport", "Transporte"


class EstimateKind(models.TextChoices):
    INITIAL = "initial", "Inicial"
    RESIDUAL = "residual", "Residual"


class HrnBand(models.TextChoices):
    NEGLIGIBLE = "negligible", "Desprezível"
    VERY_LOW = "very_low", "Muito baixo"
    LOW = "low", "Baixo"
    SIGNIFICANT = "significant", "Significante"
    HIGH = "high", "Alto"
    VERY_HIGH = "very_high", "Muito alto"
    EXTREME = "extreme", "Extremo"
    UNACCEPTABLE = "unacceptable", "Inaceitável"


class SafetyCategoryValue(models.TextChoices):
    B = "b", "B"
    C1 = "1", "1"
    C2 = "2", "2"
    C3 = "3", "3"
    C4 = "4", "4"


class PlrValue(models.TextChoices):
    A = "a", "a"
    B = "b", "b"
    C = "c", "c"
    D = "d", "d"
    E = "e", "e"


class RecommendationKind(models.TextChoices):
    NORMATIVE = "normative", "Normativa"
    PRACTICE = "practice", "Boa prática"
