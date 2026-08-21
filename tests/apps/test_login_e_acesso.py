"""Login, recuperação de senha e a tela de acesso.

O que estes testes protegem: nenhuma tela de escrita alcançável por quem não deveria, e
nenhuma resposta que revele a existência de uma conta.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse

from apps.clientes.services import criar_cliente
from apps.core.carteira import atribuir_cliente
from apps.core.enums import UserRole
from apps.core.models import ClientAssignment, Tenant, User

pytestmark = pytest.mark.django_db

SENHA = "senha-de-teste-longa-1"


@pytest.fixture
def admin(tenant_a: Tenant) -> User:
    u = User.objects.create(
        username="adm@a.com", email="adm@a.com", tenant=tenant_a, role=UserRole.ADMIN
    )
    u.set_password(SENHA)
    u.save()
    return u


@pytest.fixture
def tecnico(tenant_a: Tenant) -> User:
    u = User.objects.create(
        username="tec@a.com", email="tec@a.com", tenant=tenant_a, role=UserRole.ANALYST
    )
    u.set_password(SENHA)
    u.save()
    return u


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(legal_name="Cliente Alfa", tax_id="33333333000133", actor=engenheiro_a)


# ------------------------------------------------------------------------------ login

def test_tela_de_login_abre_sem_sessao(client) -> None:  # noqa: ANN001
    resposta = client.get(reverse("login"))
    assert resposta.status_code == 200
    assert "Entrar" in resposta.content.decode()


def test_login_com_credencial_valida_entra(client, admin: User) -> None:  # noqa: ANN001
    resposta = client.post(
        reverse("login"), {"username": admin.username, "password": SENHA}
    )
    assert resposta.status_code == 302


def test_login_errado_nao_diz_qual_campo_falhou(client, admin: User) -> None:  # noqa: ANN001
    """Dizer 'senha incorreta' confirma que o e-mail existe."""
    resposta = client.post(
        reverse("login"), {"username": admin.username, "password": "errada"}
    )
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "não conferem" in corpo


def test_area_interna_exige_sessao(client) -> None:  # noqa: ANN001
    resposta = client.get(reverse("usuarios"))
    assert resposta.status_code == 302
    assert reverse("login") in resposta.url


# ------------------------------------------------------------------ recuperação de senha

def test_recuperacao_nao_revela_se_a_conta_existe(client, admin: User) -> None:  # noqa: ANN001
    """A resposta é idêntica para e-mail existente e inexistente."""
    r_existente = client.post(reverse("recuperar_senha"), {"email": admin.email}, follow=True)
    r_inexistente = client.post(
        reverse("recuperar_senha"), {"email": "ninguem@lugar.com"}, follow=True
    )
    assert r_existente.status_code == r_inexistente.status_code == 200
    assert "Verifique seu e-mail" in r_existente.content.decode()
    assert "Verifique seu e-mail" in r_inexistente.content.decode()


def test_email_de_recuperacao_leva_a_marca_da_plataforma(client, admin: User) -> None:  # noqa: ANN001
    client.post(reverse("recuperar_senha"), {"email": admin.email})
    assert len(mail.outbox) == 1
    mensagem = mail.outbox[0]
    assert "Life Laboral" in mensagem.subject
    assert "24 horas" in mensagem.body


def test_email_nao_e_enviado_para_endereco_desconhecido(client) -> None:  # noqa: ANN001
    client.post(reverse("recuperar_senha"), {"email": "ninguem@lugar.com"})
    assert mail.outbox == []


# --------------------------------------------------------------------- tela de acesso

def test_somente_admin_abre_a_tela_de_acesso(client, tecnico: User) -> None:  # noqa: ANN001
    client.force_login(tecnico)
    resposta = client.get(reverse("usuarios"))
    assert resposta.status_code == 302  # redirecionado ao painel


def test_admin_ve_a_tela_de_acesso(client, admin: User, tecnico: User) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.get(reverse("usuarios"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert tecnico.email in corpo
    assert "sem clientes atribuídos" in corpo.lower() or "sem carteira" in corpo.lower()


def test_admin_define_carteira_pela_tela(
    client, admin: User, tecnico: User, cliente
) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.post(
        reverse("salvar_carteira", args=[tecnico.public_uuid]),
        {"clientes": [str(cliente.pk)]},
    )
    assert resposta.status_code == 302
    assert ClientAssignment.objects.filter(user=tecnico, client=cliente).exists()


def test_tecnico_nao_altera_a_propria_carteira(
    client, tecnico: User, cliente
) -> None:  # noqa: ANN001
    """A tentação óbvia: quem tem acesso restrito ampliar o próprio acesso."""
    client.force_login(tecnico)
    resposta = client.post(
        reverse("salvar_carteira", args=[tecnico.public_uuid]),
        {"clientes": [str(cliente.pk)]},
    )
    assert resposta.status_code == 302
    assert not ClientAssignment.objects.filter(user=tecnico).exists()


def test_admin_nao_altera_usuario_de_outra_organizacao(
    client, admin: User, tenant_b: Tenant
) -> None:  # noqa: ANN001
    alheio = User.objects.create(
        username="outro@b.com", email="outro@b.com", tenant=tenant_b, role=UserRole.ANALYST
    )
    client.force_login(admin)
    resposta = client.post(
        reverse("salvar_carteira", args=[alheio.public_uuid]), {"clientes": []}
    )
    assert resposta.status_code == 404


def test_barra_lateral_mostra_o_escopo(client, admin: User) -> None:  # noqa: ANN001
    """Quem vê o quê precisa ser óbvio, não descoberto ao estranhar uma lista curta."""
    client.force_login(admin)
    corpo = client.get(reverse("usuarios")).content.decode()
    assert "Toda a organização" in corpo


def test_tecnico_com_carteira_vazia_ve_o_aviso(
    client, tecnico: User, cliente
) -> None:  # noqa: ANN001
    client.force_login(tecnico)
    corpo = client.get(reverse("maquinas")).content.decode()
    assert "não tem clientes atribuídos" in corpo


def test_tecnico_com_carteira_nao_ve_o_aviso(
    client, tecnico: User, cliente, engenheiro_a, escopo_a
) -> None:  # noqa: ANN001
    atribuir_cliente(user=tecnico, client=cliente, actor=engenheiro_a)
    client.force_login(tecnico)
    corpo = client.get(reverse("maquinas")).content.decode()
    assert "não tem clientes atribuídos" not in corpo
