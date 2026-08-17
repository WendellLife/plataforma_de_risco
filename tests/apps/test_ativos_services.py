from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.ativos.enums import EnergyKind
from apps.ativos.services import (
    SerieDuplicada,
    acrescentar_fonte_de_energia,
    criar_maquina,
    definir_ponto_de_bloqueio,
)
from apps.clientes.services import criar_cliente


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(legal_name="Indústria Teste", tax_id="55555555000155", actor=engenheiro_a)


def test_d09_serie_duplicada_avisa_e_nao_bloqueia(cliente, engenheiro_a) -> None:  # noqa: ANN001
    criar_maquina(client_id=cliente.pk, name="01 - Torno", serial_number="X-1", actor=engenheiro_a)

    with pytest.raises(SerieDuplicada) as exc:
        criar_maquina(client_id=cliente.pk, name="02 - Torno", serial_number="X-1", actor=engenheiro_a)
    assert len(exc.value.maquinas) == 1

    # confirmação explícita prossegue — a duplicidade existe no acervo real
    m = criar_maquina(
        client_id=cliente.pk, name="02 - Torno", serial_number="X-1",
        confirmar_serie_duplicada=True, actor=engenheiro_a,
    )
    assert m.pk


def test_unidade_incompativel_com_tipo_de_fonte_e_recusada(cliente, engenheiro_a) -> None:  # noqa: ANN001
    m = criar_maquina(client_id=cliente.pk, name="03 - Prensa", actor=engenheiro_a)
    with pytest.raises(ValidationError):
        acrescentar_fonte_de_energia(
            machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("220"), unit="V",
            actor=engenheiro_a,
        )


def test_d01_maquina_so_libera_loto_com_todos_os_pontos(cliente, engenheiro_a) -> None:  # noqa: ANN001
    m = criar_maquina(client_id=cliente.pk, name="04 - Injetora", actor=engenheiro_a)
    eletrica = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.ELECTRIC, magnitude=Decimal("380"), unit="V", actor=engenheiro_a
    )
    pneumatica = acrescentar_fonte_de_energia(
        machine=m, kind=EnergyKind.PNEUMATIC, magnitude=Decimal("0.8"), unit="bar", actor=engenheiro_a
    )
    assert not m.pronta_para_loto
    assert m.fontes_sem_bloqueio.count() == 2

    definir_ponto_de_bloqueio(energy_source=eletrica, identifier="QE-01", actor=engenheiro_a)
    assert not m.pronta_para_loto  # ainda falta a pneumática

    definir_ponto_de_bloqueio(energy_source=pneumatica, identifier="PN-01", actor=engenheiro_a)
    assert m.pronta_para_loto
