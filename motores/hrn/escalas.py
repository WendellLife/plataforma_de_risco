"""Escalas tipadas dos quatro fatores HRN.

Domínio puro. Existe para que o fator NUNCA seja um campo numérico livre: o avaliador
escolhe um descritor da escala, e o descritor carrega o valor. É o que torna duas
apreciações comparáveis e o que permite auditar por que um fator foi escolhido
(CLAUDE.md: constante de domínio é enumeração tipada, nunca string literal).

Alterar valor ou descritor destas escalas MUDA o método: exige subir METHOD_VERSION
em motores/hrn/calculo.py, porque estimativas gravadas com versões diferentes não
são comparáveis (Espec 01, item 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .calculo import FAIXAS, Band, ROTULOS


@dataclass(frozen=True, slots=True)
class Opcao:
    valor: Decimal
    rotulo: str
    nota: str = ""

    @property
    def chave(self) -> str:
        """Valor como string canônica — é o que trafega no formulário."""
        return format(self.valor.normalize(), "f")


@dataclass(frozen=True, slots=True)
class Fator:
    sigla: str
    nome: str
    pergunta: str
    opcoes: tuple[Opcao, ...]


def _d(v: str) -> Decimal:
    return Decimal(v)


LO = Fator(
    sigla="LO",
    nome="Probabilidade de ocorrência",
    pergunta="Com o cenário atual de proteções, qual a chance de o dano ocorrer?",
    opcoes=(
        Opcao(_d("0.033"), "Praticamente impossível", "Só com falha simultânea de várias barreiras"),
        Opcao(_d("0.5"), "Muito improvável", "Concebível, sem histórico conhecido"),
        Opcao(_d("1"), "Improvável", "Possível apenas em desvio de procedimento"),
        Opcao(_d("2"), "Possível", "Já ocorreu em máquina semelhante"),
        Opcao(_d("5"), "Provável", "Ocorre com desatenção comum na tarefa"),
        Opcao(_d("8"), "Muito provável", "Depende só do acerto do operador"),
        Opcao(_d("10"), "Certo", "Ocorre sempre que a tarefa é executada"),
    ),
)

FE = Fator(
    sigla="FE",
    nome="Frequência de exposição",
    pergunta="Com que frequência alguém entra na zona de perigo?",
    opcoes=(
        Opcao(_d("0.1"), "Anualmente", "Parada programada, troca de safra"),
        Opcao(_d("0.2"), "Mensalmente", "Manutenção preventiva"),
        Opcao(_d("1"), "Semanalmente", "Limpeza profunda, setup de lote"),
        Opcao(_d("1.5"), "Diariamente", "Rotina de início ou fim de turno"),
        Opcao(_d("2.5"), "De hora em hora", "Alimentação ou retirada de peça"),
        Opcao(_d("4"), "Constantemente", "Operador permanece na zona"),
    ),
)

DPH = Fator(
    sigla="DPH",
    nome="Grau do dano possível",
    pergunta="Se ocorrer, qual o dano mais grave razoavelmente esperado?",
    opcoes=(
        Opcao(_d("0.1"), "Arranhão ou contusão", "Sem afastamento"),
        Opcao(_d("0.5"), "Laceração ou mal-estar leve", "Atendimento ambulatorial"),
        Opcao(_d("1"), "Fratura leve — dedo da mão ou do pé", "Afastamento curto"),
        Opcao(_d("2"), "Fratura grave — braço ou perna", "Afastamento prolongado"),
        Opcao(_d("4"), "Perda de um membro, um olho ou audição", "Dano permanente parcial"),
        Opcao(_d("8"), "Perda de dois membros ou dois olhos", "Invalidez"),
        Opcao(_d("15"), "Fatalidade", "Um óbito"),
    ),
)

NP = Fator(
    sigla="NP",
    nome="Número de pessoas expostas",
    pergunta="Quantas pessoas podem ser atingidas pelo mesmo evento?",
    opcoes=(
        Opcao(_d("1"), "1 a 2 pessoas"),
        Opcao(_d("2"), "3 a 7 pessoas"),
        Opcao(_d("4"), "8 a 15 pessoas"),
        Opcao(_d("8"), "16 a 50 pessoas"),
        Opcao(_d("12"), "Mais de 50 pessoas"),
    ),
)

FATORES: tuple[Fator, ...] = (LO, FE, DPH, NP)
POR_SIGLA: dict[str, Fator] = {f.sigla.lower(): f for f in FATORES}


def opcoes(sigla: str) -> tuple[Opcao, ...]:
    return POR_SIGLA[sigla.lower()].opcoes


def descritor(sigla: str, valor: Decimal) -> str:
    """Descritor escolhido, para imprimir na apreciação e no documento.

    Valor fora da escala não é erro de cálculo — é estimativa gravada por versão
    anterior do método. Devolve o número para que a origem fique visível.
    """
    for opcao in opcoes(sigla):
        if opcao.valor == valor:
            return opcao.rotulo
    return format(valor.normalize(), "f")


def escala_visual(produto: Decimal) -> list[dict[str, object]]:
    """Oito faixas em ordem, com a faixa do produto marcada — insumo da barra em tela."""
    from .calculo import faixa_de

    atual = faixa_de(produto)
    linhas: list[dict[str, object]] = []
    piso = Decimal("0")
    for band, teto in FAIXAS:
        linhas.append(
            {
                "band": str(band),
                "rotulo": ROTULOS[band],
                "de": format(piso.normalize(), "f"),
                "ate": format(teto.normalize(), "f") if teto is not None else None,
                "atual": band is atual,
            }
        )
        if teto is not None:
            piso = teto
    return linhas


def indice_da_faixa(band: Band) -> int:
    for i, (b, _) in enumerate(FAIXAS):
        if b is band:
            return i
    raise ValueError(f"faixa desconhecida: {band}")
