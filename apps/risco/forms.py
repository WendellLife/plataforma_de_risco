"""Entrada dos quatro fatores.

O formulário só valida que o valor pertence à escala tipada — o produto, a faixa e a
versão do método são decididos pelo servidor (motores/hrn), nunca enviados pelo cliente.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import forms

from motores.hrn import FATORES, Fatores


def _choices(sigla: str) -> list[tuple[str, str]]:
    from motores.hrn import opcoes

    return [(o.chave, o.rotulo) for o in opcoes(sigla)]


class FatoresForm(forms.Form):
    lo = forms.ChoiceField(label="LO", choices=lambda: _choices("lo"))
    fe = forms.ChoiceField(label="FE", choices=lambda: _choices("fe"))
    dph = forms.ChoiceField(label="DPH", choices=lambda: _choices("dph"))
    np = forms.ChoiceField(label="NP", choices=lambda: _choices("np"))

    def fatores(self) -> Fatores:
        try:
            return Fatores(
                lo=Decimal(self.cleaned_data["lo"]),
                fe=Decimal(self.cleaned_data["fe"]),
                dph=Decimal(self.cleaned_data["dph"]),
                np=Decimal(self.cleaned_data["np"]),
            )
        except (InvalidOperation, TypeError) as exc:
            raise forms.ValidationError("Fator fora da escala do método.") from exc

    @property
    def fatores_meta(self) -> tuple:
        return FATORES
