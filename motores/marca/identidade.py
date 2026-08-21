"""Identidade visual por cliente (white-label).

A decisão que define este módulo: **a marca do cliente aparece no material dele, e a marca
da consultoria nunca desaparece do documento técnico.** Um laudo assinado por engenheiro da
Life Laboral com aparência exclusiva do contratante confundiria quem responde tecnicamente
pela peça — e responsabilidade técnica confusa é problema jurídico, não estético.

Por isso a regra é assimétrica:

- **Documento impresso**: co-marca. Logo do cliente no cabeçalho, identificação da
  consultoria emissora no rodapé, sempre. O rodapé não é configurável.
- **Interface e e-mail**: pode ser do cliente, para o leitor que só acessa o próprio
  parque. Aqui o white-label é legítimo.
- **Página pública de verificação**: identidade da PLATAFORMA, nunca do cliente. Ela existe
  para um terceiro confirmar a autenticidade — parecer material do contratante enfraquece
  exatamente o que ela prova.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Superficie(StrEnum):
    INTERFACE = "interface"
    DOCUMENTO = "documento"
    EMAIL = "email"
    VERIFICACAO_PUBLICA = "verificacao_publica"


# Onde a marca do cliente pode substituir a da plataforma, e onde nunca.
PERMITE_MARCA_DO_CLIENTE: dict[Superficie, bool] = {
    Superficie.INTERFACE: True,
    Superficie.DOCUMENTO: True,   # co-marca: cabeçalho do cliente, rodapé da consultoria
    Superficie.EMAIL: True,
    Superficie.VERIFICACAO_PUBLICA: False,
}

# Paleta da plataforma. É o padrão e o piso: nenhum cliente fica sem cor definida.
PADRAO = {
    "primaria": "#43B5B6",
    "secundaria": "#0086C4",
    "tinta": "#12232e",
}

# Contraste mínimo exigido de texto sobre a cor primária (WCAG AA para texto grande).
CONTRASTE_MINIMO = 3.0


@dataclass(frozen=True, slots=True)
class Marca:
    """Identidade resolvida para uma superfície. Sempre completa — nunca com buraco."""

    nome: str
    logo_key: str = ""
    primaria: str = PADRAO["primaria"]
    secundaria: str = PADRAO["secundaria"]
    tinta: str = PADRAO["tinta"]
    texto_sobre_primaria: str = "#ffffff"
    co_marca: bool = False
    emissor: str = ""

    @property
    def tem_logo(self) -> bool:
        return bool(self.logo_key)

    def as_dict(self) -> dict[str, object]:
        return {
            "nome": self.nome, "logo_key": self.logo_key, "primaria": self.primaria,
            "secundaria": self.secundaria, "tinta": self.tinta,
            "texto_sobre_primaria": self.texto_sobre_primaria,
            "co_marca": self.co_marca, "emissor": self.emissor,
        }


def _hex_para_rgb(cor: str) -> tuple[int, int, int]:
    c = cor.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _luminancia(cor: str) -> float:
    def canal(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(v) for v in _hex_para_rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


def texto_legivel_sobre(fundo: str) -> str:
    """Escolhe preto ou branco pelo contraste real.

    Existe porque o cliente escolhe a cor, não o texto sobre ela. Deixar o texto fixo em
    branco produz botão ilegível assim que alguém escolhe um amarelo de marca.
    """
    return "#ffffff" if contraste(fundo, "#ffffff") >= contraste(fundo, PADRAO["tinta"]) else PADRAO["tinta"]


def cor_valida(cor: str) -> bool:
    if not cor or not cor.startswith("#"):
        return False
    corpo = cor.lstrip("#")
    if len(corpo) not in (3, 6):
        return False
    try:
        _hex_para_rgb(cor)
    except ValueError:
        return False
    return True


def resolver(
    *, superficie: Superficie, plataforma: str, cliente: dict[str, object] | None = None
) -> Marca:
    """Devolve a marca a aplicar. Sempre completa, com a cor de texto já decidida.

    `cliente` traz nome, logo_key e cores; qualquer campo ausente cai no padrão da
    plataforma. Nunca devolve identidade parcial — meia marca é pior que nenhuma.
    """
    if cliente is None or not PERMITE_MARCA_DO_CLIENTE[superficie]:
        return Marca(
            nome=plataforma,
            primaria=PADRAO["primaria"], secundaria=PADRAO["secundaria"], tinta=PADRAO["tinta"],
            texto_sobre_primaria=texto_legivel_sobre(PADRAO["primaria"]),
            emissor=plataforma,
        )

    primaria = str(cliente.get("primaria") or "")
    primaria = primaria if cor_valida(primaria) else PADRAO["primaria"]
    secundaria = str(cliente.get("secundaria") or "")
    secundaria = secundaria if cor_valida(secundaria) else PADRAO["secundaria"]

    return Marca(
        nome=str(cliente.get("nome") or plataforma),
        logo_key=str(cliente.get("logo_key") or ""),
        primaria=primaria,
        secundaria=secundaria,
        tinta=PADRAO["tinta"],
        texto_sobre_primaria=texto_legivel_sobre(primaria),
        # Documento é sempre co-marca: o emissor técnico não pode desaparecer.
        co_marca=superficie is Superficie.DOCUMENTO,
        emissor=plataforma,
    )


def variaveis_css(marca: Marca) -> str:
    """Bloco de custom properties para injetar na página. Só as cores que variam."""
    return (
        f"--brand-primary:{marca.primaria};"
        f"--brand-secondary:{marca.secundaria};"
        f"--brand-on-primary:{marca.texto_sobre_primaria};"
    )
