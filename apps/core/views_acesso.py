"""Administração de acesso: quem vê o quê.

Tela de produto, não do admin do Django: definir carteira é operação de rotina do gestor,
e rotina não deve morar numa interface de manutenção.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.clientes.models import Client

from .carteira import CarteiraNaoSeAplica, definir_carteira, usuarios_sem_carteira
from .convites import enviar_convite
from .enums import PERFIS_SEM_RESTRICAO_DE_CARTEIRA, UserRole
from .models import User
from .services import (
    AlteracaoDeAcessoInvalida,
    alterar_perfil,
    criar_usuario_com_acesso,
    definir_situacao,
)

# O que cada perfil significa em uma linha. Escolher perfil sem isso é escolher no escuro:
# a diferença entre analista e engenheiro não está no nome, está em quem assina.
DESCRICAO_DE_PERFIL = {
    UserRole.ADMIN: (
        "Vê toda a organização e gerencia acesso. Não publica documento assinado."
    ),
    UserRole.ENGINEER: (
        "Único perfil que publica e assina peça técnica. Vê os clientes atribuídos a ele."
    ),
    UserRole.ANALYST: (
        "Levanta risco, monta plano e prepara documento — sem publicar. Trabalha na carteira dele."
    ),
    UserRole.OPERATOR: (
        "Coleta em campo pelo aplicativo: fotos, checklist e inventário da carteira dele."
    ),
    UserRole.CLIENT_READER: (
        "Contratante. Só lê documento publicado do próprio cliente — nenhuma tela de escrita."
    ),
}


def _perfis_para_escolha() -> list[dict[str, object]]:
    return [
        {
            "valor": valor,
            "nome": rotulo,
            "descricao": DESCRICAO_DE_PERFIL[valor],
            "tem_carteira": valor not in PERFIS_SEM_RESTRICAO_DE_CARTEIRA,
        }
        for valor, rotulo in UserRole.choices
    ]


def _exige_admin(request: HttpRequest) -> bool:
    return bool(request.user.is_authenticated and request.user.ve_toda_a_organizacao)


@login_required
def lista_usuarios(request: HttpRequest) -> HttpResponse:
    if not _exige_admin(request):
        messages.error(
            request, "Somente administrador gerencia acesso — é quem responde por quem vê o quê."
        )
        return redirect("painel")

    tenant_id = request.user.tenant_id
    # Sem escopo de carteira DE PROPÓSITO: administração de acesso enxerga a organização
    # inteira, inclusive usuários que hoje não veem nada.
    # Inativos aparecem também: conta desativada não é conta apagada, e sem listá-la não
    # existe como reativar nem como auditar quem perdeu acesso.
    usuarios = list(
        User.objects.filter(tenant_id=tenant_id)
        .prefetch_related("assignments__client")
        .order_by("-is_active", "role", "first_name", "username")
    )
    clientes = list(Client.sem_escopo.filter(tenant_id=tenant_id).order_by("legal_name"))
    sem_carteira = usuarios_sem_carteira(tenant_id)

    linhas = [
        {
            "usuario": u,
            "toda_a_organizacao": u.ve_toda_a_organizacao,
            "clientes": [a.client for a in u.assignments.all()],
            "sem_carteira": u in sem_carteira,
            "somente_leitura": u.somente_leitura,
            "publica": u.pode_publicar,
            "ativo": u.is_active,
            "convite_pendente": u.is_active and not u.has_usable_password(),
            "e_voce": u.pk == request.user.pk,
        }
        for u in usuarios
    ]
    return render(
        request,
        "ui/acesso/usuarios.html",
        {
            "linhas": linhas,
            "clientes": clientes,
            "sem_carteira": sem_carteira,
            "perfis": _perfis_para_escolha(),
        },
    )


@login_required
def novo_usuario(request: HttpRequest) -> HttpResponse:
    """Criar conta é tela de produto, no mesmo lugar onde se define o que ela vê.

    Três decisões visíveis aqui:
    - a organização vem da sessão, nunca do formulário: ninguém cria conta em outra;
    - senha não é campo. A pessoa recebe convite e cria a própria;
    - perfil com carteira e nenhum cliente marcado exige confirmação explícita, em vez de
      criar em silêncio alguém que entra e não vê nada.
    """
    if not _exige_admin(request):
        messages.error(request, "Somente administrador cria usuário.")
        return redirect("painel")

    tenant_id = request.user.tenant_id
    if tenant_id is None:
        # Superusuário criado por `createsuperuser` não pertence a organização nenhuma.
        # Toda tela filtra por organização, então ele não veria nem criaria ninguém.
        messages.error(
            request,
            "Sua conta não pertence a nenhuma organização. Crie a primeira com "
            "'python manage.py criar_organizacao' — o comando também cria o administrador.",
        )
        return redirect("painel")

    clientes = list(Client.sem_escopo.filter(tenant_id=tenant_id).order_by("legal_name"))
    contexto = {
        "clientes": clientes,
        "perfis": _perfis_para_escolha(),
        "dados": {"role": UserRole.ANALYST, "clientes": []},
    }

    if request.method != "POST":
        return render(request, "ui/acesso/novo_usuario.html", contexto)

    email = (request.POST.get("email") or "").strip().lower()
    role = request.POST.get("role") or ""
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    ids = [int(v) for v in request.POST.getlist("clientes") if v.isdigit()]
    sem_acesso_confirmado = bool(request.POST.get("sem_acesso"))

    contexto["dados"] = {
        "email": email, "role": role, "first_name": first_name,
        "last_name": last_name, "clientes": ids,
    }

    erros: list[str] = []
    if not email:
        erros.append("Informe o e-mail — é por ele que a pessoa entra e recebe o convite.")
    if role not in UserRole.values:
        erros.append("Escolha um perfil.")
    elif role not in PERFIS_SEM_RESTRICAO_DE_CARTEIRA and not ids and not sem_acesso_confirmado:
        erros.append(
            "Este perfil vê apenas os clientes atribuídos. Sem nenhum cliente marcado, a "
            "pessoa entra e encontra todas as telas vazias — marque os clientes ou "
            "confirme a criação sem acesso."
        )
    if email and User.objects.filter(tenant_id=tenant_id, email__iexact=email).exists():
        erros.append(f"Já existe uma conta com {email} nesta organização.")

    if erros:
        contexto["erros"] = erros
        contexto["pedir_confirmacao"] = any("confirme a criação" in e for e in erros)
        return render(request, "ui/acesso/novo_usuario.html", contexto, status=422)

    try:
        usuario = criar_usuario_com_acesso(
            tenant=request.user.tenant, email=email, role=role,
            first_name=first_name, last_name=last_name,
            client_ids=ids, actor=request.user,
        )
    except (ValidationError, CarteiraNaoSeAplica) as erro:
        contexto["erros"] = getattr(erro, "messages", [str(erro)])
        return render(request, "ui/acesso/novo_usuario.html", contexto, status=422)

    enviado = enviar_convite(user=usuario, request=request, remetente=request.user)
    if usuario.ve_toda_a_organizacao:
        escopo = "vê toda a organização"
    elif ids:
        escopo = f"vê {len(ids)} cliente(s)"
    else:
        escopo = "ainda não vê nenhum cliente"
    messages.success(
        request,
        f"{usuario} criado como {usuario.get_role_display()} e {escopo}. "
        + (
            "Convite enviado para criar a senha."
            if enviado
            else "Sem e-mail cadastrado: o convite não pôde ser enviado."
        ),
    )
    return redirect("usuarios")


def _usuario_da_organizacao(request: HttpRequest, uuid: str) -> User:
    return get_object_or_404(
        User.objects.filter(tenant_id=request.user.tenant_id), public_uuid=uuid
    )


@login_required
@require_POST
def salvar_perfil(request: HttpRequest, uuid: str) -> HttpResponse:
    if not _exige_admin(request):
        messages.error(request, "Somente administrador altera perfil.")
        return redirect("painel")

    usuario = _usuario_da_organizacao(request, uuid)
    role = request.POST.get("role") or ""
    if role not in UserRole.values:
        messages.error(request, "Perfil inválido.")
        return redirect("usuarios")
    try:
        alterar_perfil(user=usuario, role=role, actor=request.user)
    except AlteracaoDeAcessoInvalida as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request, f"{usuario} agora é {usuario.get_role_display()}."
        )
    return redirect("usuarios")


@login_required
@require_POST
def salvar_situacao(request: HttpRequest, uuid: str) -> HttpResponse:
    if not _exige_admin(request):
        messages.error(request, "Somente administrador ativa ou desativa conta.")
        return redirect("painel")

    usuario = _usuario_da_organizacao(request, uuid)
    ativo = request.POST.get("ativo") == "1"
    try:
        definir_situacao(user=usuario, ativo=ativo, actor=request.user)
    except AlteracaoDeAcessoInvalida as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{usuario} reativado — sem carteira até receber acesso de novo."
            if ativo
            else f"{usuario} desativado. A conta e a trilha de auditoria ficam.",
        )
    return redirect("usuarios")


@login_required
@require_POST
def reenviar_convite(request: HttpRequest, uuid: str) -> HttpResponse:
    if not _exige_admin(request):
        messages.error(request, "Somente administrador reenvia convite.")
        return redirect("painel")

    usuario = _usuario_da_organizacao(request, uuid)
    if enviar_convite(user=usuario, request=request, remetente=request.user):
        messages.success(request, f"Novo convite enviado para {usuario.email}.")
    else:
        messages.error(request, f"{usuario} não tem e-mail cadastrado.")
    return redirect("usuarios")


@login_required
@require_POST
def salvar_carteira(request: HttpRequest, uuid: str) -> HttpResponse:
    if not _exige_admin(request):
        messages.error(request, "Somente administrador altera carteira de acesso.")
        return redirect("painel")

    usuario = get_object_or_404(
        User.objects.filter(tenant_id=request.user.tenant_id), public_uuid=uuid
    )
    ids = [int(v) for v in request.POST.getlist("clientes") if v.isdigit()]
    try:
        final = definir_carteira(user=usuario, client_ids=ids, actor=request.user)
    except CarteiraNaoSeAplica as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{usuario} agora vê {len(final)} cliente(s)."
            if final
            else f"{usuario} ficou sem nenhum cliente — não verá dado algum até receber acesso.",
        )
    return redirect("usuarios")


class Login(auth_views.LoginView):
    """Entrada. O template leva a marca da PLATAFORMA, nunca a de um cliente.

    Quem está na tela de login ainda não foi identificado — não há como saber de que
    cliente ele é, e chutar seria pior que não aplicar marca alguma.
    """

    template_name = "ui/acesso/login.html"
    redirect_authenticated_user = True


class RecuperarSenha(auth_views.PasswordResetView):
    """Redefinição por e-mail.

    Nunca revela se o endereço existe: a tela responde igual nos dois casos. É proteção de
    privacidade — confirmar a existência de uma conta é vazamento de informação.
    """

    template_name = "ui/acesso/recuperar.html"
    email_template_name = "email/recuperar_senha.txt"
    html_email_template_name = "email/recuperar_senha.html"
    subject_template_name = "email/recuperar_senha_assunto.txt"
    success_url = "/acesso/recuperar/enviado"

    def get_context_data(self, **kwargs):  # noqa: ANN001, ANN003, ANN201
        contexto = super().get_context_data(**kwargs)
        contexto["enviado"] = False
        return contexto


class RecuperarSenhaEnviado(auth_views.PasswordResetDoneView):
    template_name = "ui/acesso/recuperar.html"
    extra_context = {"enviado": True}


class NovaSenha(auth_views.PasswordResetConfirmView):
    """Destino do link do e-mail. Token de uso único, validade de 24 h."""

    template_name = "ui/acesso/nova_senha.html"
    success_url = "/acesso/nova-senha/pronto"


class NovaSenhaPronta(auth_views.PasswordResetCompleteView):
    template_name = "ui/acesso/nova_senha.html"
    extra_context = {"concluido": True}
