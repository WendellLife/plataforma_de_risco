"""Escopo de acesso: organização e carteira de clientes.

O que estes testes protegem é a diferença entre duas coisas que parecem iguais no código e
são opostas no efeito: `None` (vê tudo) e `frozenset()` (vê nada). Trocar uma pela outra é
o erro mais fácil e mais grave desta camada.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.apps import apps

from apps.ativos.models import Machine
from apps.clientes.models import Client
from apps.clientes.services import criar_cliente
from apps.core.carteira import (
    CarteiraNaoSeAplica,
    atribuir_cliente,
    definir_carteira,
    remover_cliente,
    usuarios_sem_carteira,
)
from apps.core.enums import UserRole
from apps.core.models import ClientAssignment, Tenant, User
from apps.core.tenancy import usando_escopo, usando_tenant
from apps.documentos.models import Document
from apps.risco.models import Hazard

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario(tenant_a: Tenant, escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    """Dois clientes com uma máquina cada — o mínimo para provar isolamento parcial."""
    alfa = criar_cliente(legal_name="Cliente Alfa", tax_id="11111111000111", actor=engenheiro_a)
    beta = criar_cliente(legal_name="Cliente Beta", tax_id="22222222000122", actor=engenheiro_a)
    m_alfa = Machine.objects.create(tenant=tenant_a, client=alfa, name="Prensa Alfa")
    m_beta = Machine.objects.create(tenant=tenant_a, client=beta, name="Serra Beta")
    Hazard.objects.create(
        tenant=tenant_a, machine=m_alfa, zone="Zona Alfa", title="Perigo Alfa",
        iso12100_type="mechanical",
    )
    Hazard.objects.create(
        tenant=tenant_a, machine=m_beta, zone="Zona Beta", title="Perigo Beta",
        iso12100_type="mechanical",
    )
    return {"alfa": alfa, "beta": beta, "m_alfa": m_alfa, "m_beta": m_beta}


@pytest.fixture
def tecnico(tenant_a: Tenant) -> User:
    return User.objects.create(
        username="tec@a.com", email="tec@a.com", tenant=tenant_a, role=UserRole.ANALYST
    )


@pytest.fixture
def admin(tenant_a: Tenant) -> User:
    return User.objects.create(
        username="adm@a.com", email="adm@a.com", tenant=tenant_a, role=UserRole.ADMIN
    )


# ------------------------------------------------------------------- carteira do usuário

def test_admin_ve_toda_a_organizacao(admin: User, escopo_a) -> None:  # noqa: ANN001
    assert admin.ve_toda_a_organizacao
    assert admin.carteira() is None  # None = sem restrição


def test_tecnico_sem_atribuicao_nao_ve_nada(tecnico: User, escopo_a) -> None:  # noqa: ANN001
    """O padrão é seguro: quem não recebeu acesso não tem acesso."""
    assert not tecnico.ve_toda_a_organizacao
    assert tecnico.carteira() == frozenset()


def test_carteira_vazia_e_diferente_de_carteira_ausente(
    tecnico: User, admin: User, escopo_a
) -> None:  # noqa: ANN001
    """A distinção que sustenta a camada inteira."""
    assert admin.carteira() is None
    assert tecnico.carteira() is not None
    assert len(tecnico.carteira()) == 0


def test_atribuir_cliente_forma_a_carteira(
    tecnico: User, cenario, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    assert tecnico.carteira() == frozenset({cenario["alfa"].pk})


def test_atribuir_a_admin_e_recusado(admin: User, cenario, engenheiro_a, escopo_a) -> None:  # noqa: ANN001
    """Dar carteira a quem vê tudo sugeriria uma restrição inexistente."""
    with pytest.raises(CarteiraNaoSeAplica):
        atribuir_cliente(user=admin, client=cenario["alfa"], actor=engenheiro_a)


def test_atribuicao_e_idempotente(tecnico: User, cenario, engenheiro_a, escopo_a) -> None:  # noqa: ANN001
    atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    assert ClientAssignment.objects.filter(user=tecnico).count() == 1


def test_remover_acesso_encolhe_a_carteira(
    tecnico: User, cenario, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    atribuir_cliente(user=tecnico, client=cenario["beta"], actor=engenheiro_a)
    assert remover_cliente(user=tecnico, client=cenario["beta"], actor=engenheiro_a)
    assert tecnico.carteira() == frozenset({cenario["alfa"].pk})


def test_definir_carteira_substitui_o_conjunto(
    tecnico: User, cenario, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    final = definir_carteira(
        user=tecnico, client_ids=[cenario["beta"].pk], actor=engenheiro_a
    )
    assert final == frozenset({cenario["beta"].pk})
    assert tecnico.carteira() == frozenset({cenario["beta"].pk})


def test_definir_carteira_ignora_cliente_de_outra_organizacao(
    tecnico: User, cenario, tenant_b: Tenant, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    alheio = Client.objects.create(
        tenant=tenant_b, legal_name="De Outra Org", tax_id="99999999000199"
    )
    final = definir_carteira(
        user=tecnico, client_ids=[cenario["alfa"].pk, alheio.pk], actor=engenheiro_a
    )
    assert final == frozenset({cenario["alfa"].pk})


def test_usuarios_sem_carteira_sao_listados_para_aviso(
    tecnico: User, admin: User, tenant_a: Tenant, escopo_a
) -> None:  # noqa: ANN001
    """Efeito colateral previsível do padrão seguro: a tela avisa em vez de afrouxar."""
    sem = usuarios_sem_carteira(tenant_a.pk)
    assert tecnico in sem
    assert admin not in sem


# ------------------------------------------------------------------ efeito nas consultas

def test_carteira_filtra_maquinas(tecnico: User, cenario, engenheiro_a, tenant_a) -> None:  # noqa: ANN001
    with usando_tenant(tenant_a.pk):
        atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    with usando_escopo(tenant_a.pk, tecnico.carteira()):
        nomes = set(Machine.objects.values_list("name", flat=True))
    assert nomes == {"Prensa Alfa"}


def test_carteira_filtra_por_caminho_indireto(
    tecnico: User, cenario, engenheiro_a, tenant_a
) -> None:  # noqa: ANN001
    """Hazard chega ao cliente por machine__client — o filtro precisa atravessar."""
    with usando_tenant(tenant_a.pk):
        atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    with usando_escopo(tenant_a.pk, tecnico.carteira()):
        titulos = set(Hazard.objects.values_list("title", flat=True))
    assert titulos == {"Perigo Alfa"}


def test_carteira_vazia_nao_devolve_nada(tecnico: User, cenario, tenant_a) -> None:  # noqa: ANN001
    """O caso perigoso: conjunto vazio NÃO pode virar 'sem filtro'."""
    with usando_escopo(tenant_a.pk, frozenset()):
        assert Machine.objects.count() == 0
        assert Hazard.objects.count() == 0
        assert Document.objects.count() == 0


def test_sem_restricao_ve_todos_os_clientes(cenario, tenant_a) -> None:  # noqa: ANN001
    with usando_escopo(tenant_a.pk, None):
        assert Machine.objects.count() == 2


def test_cliente_e_filtrado_por_chave_primaria(
    tecnico: User, cenario, engenheiro_a, tenant_a
) -> None:  # noqa: ANN001
    with usando_tenant(tenant_a.pk):
        atribuir_cliente(user=tecnico, client=cenario["alfa"], actor=engenheiro_a)
    with usando_escopo(tenant_a.pk, tecnico.carteira()):
        assert set(Client.objects.values_list("legal_name", flat=True)) == {"Cliente Alfa"}


def test_fila_herda_organizacao_sem_carteira(cenario, tenant_a) -> None:  # noqa: ANN001
    """A fila trabalha pela organização, não por uma pessoa.

    Compor o PDF de um documento não pode falhar porque quem publicou tem carteira
    restrita — por isso `usando_tenant` zera a restrição de propósito.
    """
    with usando_escopo(tenant_a.pk, frozenset()):
        assert Machine.objects.count() == 0
        with usando_tenant(tenant_a.pk):
            assert Machine.objects.count() == 2


# ------------------------------------------------------- guarda-corpo estrutural

def test_toda_tabela_com_dado_de_cliente_declara_o_caminho() -> None:
    """Impede que uma tabela nova escape do escopo por esquecimento.

    Sem `caminho_para_cliente`, o filtro de carteira NÃO é aplicado — silenciosamente. Se
    você adicionou um modelo e este teste falhou, decida conscientemente: declare o
    caminho, ou acrescente o modelo à lista de exceções abaixo com o motivo.
    """
    # Tabelas sem vínculo com cliente, por natureza — cada uma com sua razão.
    excecoes = {
        "core.Tenant",            # a própria organização
        "core.User",              # pessoa, não dado de cliente
        "core.ClientAssignment",  # define a carteira; filtrar por ela seria circular
        "core.AuditLog",          # trilha da organização, lida com filtro explícito
        "clientes.Person",        # pessoa do tenant, atende vários clientes
        "checklists.MachineType", # biblioteca compartilhada
        "checklists.LibraryItem", # biblioteca normativa, global
        "campo.Device",           # aparelho é do operador
        "campo.SyncBatch",        # envelope de transporte, pode cruzar clientes
        "campo.SyncRecord",       # idem
    }
    from apps.core.models import RegistroTenant

    faltando = []
    for model in apps.get_models():
        if not issubclass(model, RegistroTenant):
            continue
        etiqueta = f"{model._meta.app_label}.{model.__name__}"
        if etiqueta in excecoes:
            continue
        if getattr(model, "caminho_para_cliente", None) is None:
            faltando.append(etiqueta)
    assert not faltando, (
        "Modelos sem 'caminho_para_cliente' e fora da lista de exceções: "
        f"{sorted(faltando)}. Declare o caminho ou justifique a exceção no teste."
    )


def test_isolamento_entre_organizacoes_continua_valendo(
    cenario, tenant_a: Tenant, tenant_b: Tenant
) -> None:  # noqa: ANN001
    """A carteira é camada ADICIONAL — não substitui o isolamento por organização."""
    with usando_escopo(tenant_b.pk, None):
        assert Machine.objects.count() == 0
