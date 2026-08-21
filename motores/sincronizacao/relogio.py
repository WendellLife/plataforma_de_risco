"""Relógio do aparelho.

O aparelho de campo trabalha offline por horas e pode ter o relógio errado. A data
enviada é o que o analista viu; a hora de recepção é o que o servidor testemunhou. As
duas são gravadas, e a divergência é registrada como AVISO — nunca corrigida em
silêncio, porque a data da coleta é conteúdo de laudo (Espec 08, item 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DESVIO_TOLERADO = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class DesvioDeRelogio:
    segundos: int
    tolerado: bool

    @property
    def mensagem(self) -> str:
        minutos = abs(self.segundos) // 60
        adiantado = "adiantado" if self.segundos > 0 else "atrasado"
        return (
            f"Relógio do aparelho {adiantado} em {minutos} min em relação ao servidor — "
            "a data informada foi preservada e a hora de recepção também está registrada."
        )


class SemFusoHorario(ValueError):
    """Data sem fuso não é aceita: não há como saber a que instante se refere."""


def conferir_relogio(*, informado: datetime, recebido: datetime) -> DesvioDeRelogio:
    if informado.tzinfo is None or informado.utcoffset() is None:
        raise SemFusoHorario("Toda data enviada pelo aparelho precisa carregar fuso horário.")
    delta = informado - recebido
    return DesvioDeRelogio(
        segundos=int(delta.total_seconds()), tolerado=abs(delta) <= DESVIO_TOLERADO
    )
