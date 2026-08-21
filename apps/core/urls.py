from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import painel
from .views_acesso import (
    Login,
    NovaSenha,
    NovaSenhaPronta,
    RecuperarSenha,
    RecuperarSenhaEnviado,
    lista_usuarios,
    novo_usuario,
    reenviar_convite,
    salvar_carteira,
    salvar_perfil,
    salvar_situacao,
)

urlpatterns = [
    path("", painel, name="painel"),
    path("entrar", Login.as_view(), name="login"),
    path("sair", LogoutView.as_view(next_page="login"), name="logout"),
    path("acesso/recuperar", RecuperarSenha.as_view(), name="recuperar_senha"),
    path("acesso/recuperar/enviado", RecuperarSenhaEnviado.as_view(), name="recuperar_enviado"),
    # O nome 'password_reset_confirm' é exigido pelo Django ao montar o link do e-mail.
    path(
        "acesso/nova-senha/<uidb64>/<token>/",
        NovaSenha.as_view(),
        name="password_reset_confirm",
    ),
    path("acesso/nova-senha/pronto", NovaSenhaPronta.as_view(), name="nova_senha_pronta"),
    path("acesso/", lista_usuarios, name="usuarios"),
    path("acesso/novo", novo_usuario, name="novo_usuario"),
    path("acesso/<uuid:uuid>/carteira", salvar_carteira, name="salvar_carteira"),
    path("acesso/<uuid:uuid>/perfil", salvar_perfil, name="salvar_perfil"),
    path("acesso/<uuid:uuid>/situacao", salvar_situacao, name="salvar_situacao"),
    path("acesso/<uuid:uuid>/convite", reenviar_convite, name="reenviar_convite"),
]
