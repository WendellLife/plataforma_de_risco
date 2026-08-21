"""Percentual de adequação. Domínio puro.

A pergunta que este motor responde é a que o cliente faz na reunião: *quanto do que foi
apontado já foi resolvido?* Três decisões que impedem a resposta de ser cosmética:

1. **O denominador é toda ação do escopo**, inclusive as canceladas com justificativa —
   cancelar não some do histórico. Só ação concluída soma no numerador.
2. **Ação parcialmente feita não conta como meia adequação.** Diferente do checklist
   (onde "parcial" pesa 0,5), aqui a proteção existe ou não existe. Meio interbloqueio
   não protege ninguém.
3. **A data que vale é a do FATO**, não a do lançamento. Quem registra em setembro uma
   proteção instalada em agosto tem a adequação recalculada em agosto — é o que faz a
   curva de evolução ser auditável.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Existe para deixar a decisão nº 2 explícita e testável: não há peso fracionário.
PESO_SITUACAO: dict[str, Decimal] = {
    "concluida": Decimal("1"),
    "aberta": Decimal("0"),
    "em_execucao": Decimal("0"),
    "a_vencer": Decimal("0"),
    "vencida": Decimal("0"),
    "cancelada": Decimal("0"),
}


@dataclass(frozen=True, slots=True)
class Adequacao:
    total: int
    concluidas: int
    vencidas: int
    canceladas: int
    percentual: Decimal
    ate: date | None = None

    @property
    def pendentes(self) -> int:
        return self.total - self.concluidas - self.canceladas

    @property
    def sem_acoes(self) -> bool:
        return self.total == 0


def calcular_adequacao(
    situacoes: list[str], *, concluidas_ate: list[date] | None = None, ate: date | None = None
) -> Adequacao:
    """Percentual de ações concluídas.

    Passando `ate`, o cálculo é histórico: conta apenas conclusões cuja DATA DO FATO é
    anterior ou igual ao corte. É assim que a curva de evolução é reconstruída sem
    depender de quando alguém digitou.
    """
    total = len(situacoes)
    if total == 0:
        return Adequacao(
            total=0, concluidas=0, vencidas=0, canceladas=0, percentual=Decimal("0.0"), ate=ate
        )

    if ate is not None and concluidas_ate is not None:
        concluidas = sum(1 for d in concluidas_ate if d is not None and d <= ate)
    else:
        concluidas = sum(1 for s in situacoes if s == "concluida")

    return Adequacao(
        total=total,
        concluidas=concluidas,
        vencidas=sum(1 for s in situacoes if s == "vencida"),
        canceladas=sum(1 for s in situacoes if s == "cancelada"),
        percentual=(Decimal(concluidas) / Decimal(total) * 100).quantize(Decimal("0.1")),
        ate=ate,
    )
