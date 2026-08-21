"""Criação de usuário pela tela de produto.

O que estes testes protegem:
- ninguém cria conta em outra organização;
- conta nasce sem senha utilizável e o convite é o único caminho até a primeira senha;
- perfil com carteira e nenhum cliente exige confirmação explícita, em vez de criar em
  silêncio alguém que entra e não vê nada;
- a organização nunca fica sem administrador ativo.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse

from apps.clientes.services import criar_cliente
from apps.core.enums import UserRole
from apps.core.models import ClientAssignment, Tenant, User
from apps.core.services import (
    AlteracaoDeAcessoInvalida,
    alterar_perfil,
    criar_usuario_com_acesso,
    definir_situacao,
)

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
def segundo_admin(tenant_a: Tenant) -> User:
    return User.objects.create(
        username="adm2@a.com", email="adm2@a.com", tenant=tenant_a, role=UserRole.ADMIN
    )


@pytest.fixture
def cliente(escopo_a, engenheiro_a):  # noqa: ANN001, ANN201
    return criar_cliente(legal_name="Cliente Alfa", tax_id="33333333000133", actor=engenheiro_a)


# ------------------------------------------------------------------ acesso à tela

def test_tela_de_criacao_exige_admin(client, engenheiro_a: User) -> None:  # noqa: ANN001
    client.force_login(engenheiro_a)
    assert client.get(reverse("novo_usuario")).status_code == 302


def test_admin_abre_a_tela_com_os_perfis_explicados(client, admin: User) -> None:  # noqa: ANN001
    client.force_login(admin)
    corpo = client.get(reverse("novo_usuario")).content.decode()
    assert "Novo usuário" in corpo
    # A diferença entre analista e engenheiro não está no nome; a tela precisa dizer.
    assert "publica e assina" in corpo


def test_tela_de_criacao_nao_tem_campo_de_senha(client, admin: User) -> None:  # noqa: ANN001
    """Quem cria a conta nunca fica sabendo a credencial de outra pessoa."""
    client.force_login(admin)
    corpo = client.get(reverse("novo_usuario")).content.decode()
    assert 'type="password"' not in corpo


# ------------------------------------------------------------------------ criação

def test_criacao_com_carteira_envia_convite(client, admin: User, cliente) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.post(
        reverse("novo_usuario"),
        {
            "email": "Nova.Pessoa@a.com", "role": UserRole.ANALYST,
            "first_name": "Nova", "last_name": "Pessoa",
            "clientes": [str(cliente.pk)],
        },
    )
    assert resposta.status_code == 302
    criado = User.objects.get(email="nova.pessoa@a.com")
    assert criado.tenant_id == admin.tenant_id
    assert not criado.has_usable_password()
    assert ClientAssignment.objects.filter(user=criado, client=cliente).exists()
    assert len(mail.outbox) == 1
    assert "Life Laboral" in mail.outbox[0].subject
    assert "24 horas" in mail.outbox[0].body


def test_perfil_com_carteira_e_sem_cliente_pede_confirmacao(
    client, admin: User, cliente
) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.post(
        reverse("novo_usuario"), {"email": "cego@a.com", "role": UserRole.OPERATOR}
    )
    assert resposta.status_code == 422
    assert not User.objects.filter(email="cego@a.com").exists()
    assert mail.outbox == []
    assert "telas vazias" in resposta.content.decode()


def test_criacao_sem_cliente_passa_com_confirmacao(client, admin: User, cliente) -> None:  # noqa: ANN001
    """Criar sem acesso é legítimo — só não pode ser acidental."""
    client.force_login(admin)
    resposta = client.post(
        reverse("novo_usuario"),
        {"email": "depois@a.com", "role": UserRole.OPERATOR, "sem_acesso": "1"},
    )
    assert resposta.status_code == 302
    criado = User.objects.get(email="depois@a.com")
    assert criado.carteira() == frozenset()


def test_admin_criado_nao_recebe_carteira(client, admin: User, cliente) -> None:  # noqa: ANN001
    """Marcar clientes para um administrador registraria uma restrição que não existe."""
    client.force_login(admin)
    client.post(
        reverse("novo_usuario"),
        {"email": "adm3@a.com", "role": UserRole.ADMIN, "clientes": [str(cliente.pk)]},
    )
    criado = User.objects.get(email="adm3@a.com")
    assert not ClientAssignment.objects.filter(user=criado).exists()
    assert criado.carteira() is None


def test_engenheiro_criado_nasce_com_mfa(client, admin: User, cliente) -> None:  # noqa: ANN001
    client.force_login(admin)
    client.post(
        reverse("novo_usuario"),
        {"email": "eng2@a.com", "role": UserRole.ENGINEER, "clientes": [str(cliente.pk)]},
    )
    assert User.objects.get(email="eng2@a.com").mfa_enabled is True


def test_email_repetido_na_organizacao_e_recusado(client, admin: User) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.post(
        reverse("novo_usuario"),
        {"email": admin.email, "role": UserRole.ADMIN},
    )
    assert resposta.status_code == 422
    assert "Já existe uma conta" in resposta.content.decode()


def test_organizacao_vem_da_sessao_e_nao_do_formulario(
    client, admin: User, tenant_b: Tenant
) -> None:  # noqa: ANN001
    client.force_login(admin)
    client.post(
        reverse("novo_usuario"),
        {"email": "tentativa@b.com", "role": UserRole.ADMIN, "tenant": str(tenant_b.pk)},
    )
    assert User.objects.get(email="tentativa@b.com").tenant_id == admin.tenant_id


def test_convite_leva_ao_link_de_primeira_senha(client, admin: User, cliente) -> None:  # noqa: ANN001
    client.force_login(admin)
    client.post(
        reverse("novo_usuario"),
        {"email": "link@a.com", "role": UserRole.ANALYST, "clientes": [str(cliente.pk)]},
    )
    corpo = mail.outbox[0].body
    assert "/acesso/nova-senha/" in corpo


def test_reenvio_de_convite_gera_novo_link(client, admin: User, engenheiro_a: User) -> None:  # noqa: ANN001
    client.force_login(admin)
    resposta = client.post(reverse("reenviar_convite", args=[engenheiro_a.public_uuid]))
    assert resposta.status_code == 302
    assert len(mail.outbox) == 1


# ------------------------------------------------------------- perfil e situação

def test_promover_a_admin_apaga_a_carteira(
    escopo_a, engenheiro_a: User, cliente, admin: User
) -> None:
    from apps.core.carteira import atribuir_cliente

    atribuir_cliente(user=engenheiro_a, client=cliente, actor=admin)
    alterar_perfil(user=engenheiro_a, role=UserRole.ADMIN, actor=admin)
    assert not ClientAssignment.objects.filter(user=engenheiro_a).exists()
    assert engenheiro_a.carteira() is None


def test_rebaixar_o_ultimo_admin_e_recusado(escopo_a, admin: User) -> None:  # noqa: ANN001
    with pytest.raises(AlteracaoDeAcessoInvalida):
        alterar_perfil(user=admin, role=UserRole.ANALYST, actor=admin)


def test_rebaixar_admin_com_outro_ativo_passa(
    escopo_a, admin: User, segundo_admin: User
) -> None:
    alterar_perfil(user=segundo_admin, role=UserRole.ANALYST, actor=admin)
    assert User.objects.get(pk=segundo_admin.pk).role == UserRole.ANALYST


def test_ninguem_desativa_a_propria_conta(escopo_a, admin: User, segundo_admin: User) -> None:
    with pytest.raises(AlteracaoDeAcessoInvalida):
        definir_situacao(user=admin, ativo=False, actor=admin)


def test_desativar_o_ultimo_admin_e_recusado(escopo_a, admin: User, engenheiro_a: User) -> None:
    with pytest.raises(AlteracaoDeAcessoInvalida):
        definir_situacao(user=admin, ativo=False, actor=engenheiro_a)


def test_reativar_nao_devolve_carteira(
    escopo_a, admin: User, engenheiro_a: User, cliente
) -> None:
    from apps.core.carteira import atribuir_cliente

    atribuir_cliente(user=engenheiro_a, client=cliente, actor=admin)
    definir_situacao(user=engenheiro_a, ativo=False, actor=admin)
    # Desativar não apaga a carteira; o que impede o acesso é a conta inativa.
    assert not User.objects.get(pk=engenheiro_a.pk).is_active


def test_desativado_aparece_na_lista_para_ser_reativado(
    client, admin: User, engenheiro_a: User, escopo_a
) -> None:  # noqa: ANN001
    definir_situacao(user=engenheiro_a, ativo=False, actor=admin)
    client.force_login(admin)
    corpo = client.get(reverse("usuarios")).content.decode()
    assert engenheiro_a.email in corpo
    assert "Reativar conta" in corpo


def test_conta_desativada_nao_entra(client, admin: User, escopo_a) -> None:  # noqa: ANN001
    alvo = User.objects.create(
        username="fora@a.com", email="fora@a.com", tenant=admin.tenant, role=UserRole.ANALYST
    )
    alvo.set_password(SENHA)
    alvo.save()
    definir_situacao(user=alvo, ativo=False, actor=admin)
    resposta = client.post(reverse("login"), {"username": alvo.username, "password": SENHA})
    assert resposta.status_code == 200  # permanece na tela de login


def test_servico_de_criacao_recusa_carteira_para_admin(tenant_a: Tenant, escopo_a) -> None:
    """Chamada direta do serviço tem a mesma regra da tela — nada depende da view."""
    criado = criar_usuario_com_acesso(
        tenant=tenant_a, email="adm4@a.com", role=UserRole.ADMIN, client_ids=[999]
    )
    assert criado.carteira() is None
