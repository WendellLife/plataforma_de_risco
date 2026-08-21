"""Prazo e vencimento de ação corretiva. Domínio puro.

Duas decisões de domínio vivem aqui:

**O prazo nasce do risco, não do calendário.** Uma zona de HRN 900 e outra de HRN 8 não
podem receber o mesmo prazo por padrão. A tabela abaixo traduz faixa de HRN em dias, e é
uma SUGESTÃO — quem responde pela obra pode encurtar ou justificar um prazo maior, mas
nunca receber um número inventado pela tela.

**Vencido é um fato, não um estado gravado.** Nenhum campo "atrasada" no banco: a
situação é derivada da data de hoje a cada leitura. Estado gravado exigiria um job
noturno para envelhecer registros e ficaria errado entre execuções.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

# Faixa de HRN (teto) → dias de prazo. None = acima de tudo.
PRAZO_POR_FAIXA: tuple[tuple[Decimal | None, int], ...] = (
    (Decimal("5"), 180),      # desprezível e muito baixo
    (Decimal("10"), 120),     # baixo
    (Decimal("50"), 90),      # significativo
    (Decimal("100"), 45),     # alto
    (Decimal("500"), 20),     # muito alto
    (Decimal("1000"), 7),     # extremo
    (None, 3),                # inaceitável — dias, não semanas
)

DIAS_DE_ALERTA = 15


class Situacao(StrEnum):
    """Situação DERIVADA. Nunca gravada em coluna."""

    ABERTA = "aberta"
    EM_EXECUCAO = "em_execucao"
    A_VENCER = "a_vencer"
    VENCIDA = "vencida"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"


ROTULOS: dict[Situacao, str] = {
    Situacao.ABERTA: "Aberta",
    Situacao.EM_EXECUCAO: "Em execução",
    Situacao.A_VENCER: "A vencer",
    Situacao.VENCIDA: "Vencida",
    Situacao.CONCLUIDA: "Concluída",
    Situacao.CANCELADA: "Cancelada",
}


@dataclass(frozen=True, slots=True)
class Vencimento:
    situacao: Situacao
    dias_restantes: int | None

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.situacao]

    @property
    def exige_atencao(self) -> bool:
        return self.situacao in (Situacao.VENCIDA, Situacao.A_VENCER)

    @property
    def mensagem(self) -> str:
        if self.situacao is Situacao.VENCIDA:
            dias = abs(self.dias_restantes or 0)
            return f"Vencida há {dias} dia(s) — precisa de nova data com justificativa."
        if self.situacao is Situacao.A_VENCER:
            return f"Vence em {self.dias_restantes} dia(s)."
        return ""


def prazo_sugerido(hrn: Decimal | None, *, a_partir_de: date | None = None) -> date | None:
    """Data sugerida a partir da faixa de HRN. Sem HRN não há sugestão — e não se inventa."""
    if hrn is None:
        return None
    base = a_partir_de or date.today()
    for teto, dias in PRAZO_POR_FAIXA:
        if teto is None or hrn <= teto:
            return base + timedelta(days=dias)
    return base


def dias_sugeridos(hrn: Decimal | None) -> int | None:
    if hrn is None:
        return None
    for teto, dias in PRAZO_POR_FAIXA:
        if teto is None or hrn <= teto:
            return dias
    return None


def classificar_vencimento(
    *, prazo: date | None, concluida_em: date | None = None, cancelada: bool = False,
    iniciada: bool = False, hoje: date | None = None,
) -> Vencimento:
    if cancelada:
        return Vencimento(situacao=Situacao.CANCELADA, dias_restantes=None)
    if concluida_em is not None:
        return Vencimento(situacao=Situacao.CONCLUIDA, dias_restantes=None)
    if prazo is None:
        return Vencimento(
            situacao=Situacao.EM_EXECUCAO if iniciada else Situacao.ABERTA, dias_restantes=None
        )
    restantes = (prazo - (hoje or date.today())).days
    if restantes < 0:
        return Vencimento(situacao=Situacao.VENCIDA, dias_restantes=restantes)
    if restantes <= DIAS_DE_ALERTA:
        return Vencimento(situacao=Situacao.A_VENCER, dias_restantes=restantes)
    return Vencimento(
        situacao=Situacao.EM_EXECUCAO if iniciada else Situacao.ABERTA, dias_restantes=restantes
    )
