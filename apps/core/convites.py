"""Convite de acesso.

A decisão que este módulo protege: **ninguém digita a senha de outra pessoa**. O usuário
nasce sem senha utilizável e recebe um link de uso único para criar a sua. O administrador
cria a conta e define o que ela vê — nunca fica sabendo a credencial.

O link é o mesmo mecanismo da recuperação de senha (token de uso único, 24 h). O que muda
é o texto: quem recebe não está recuperando acesso, está descobrindo que tem acesso.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


def _dominio(request: HttpRequest | None) -> tuple[str, str]:
    if request is not None:
        return ("https" if request.is_secure() else "http"), request.get_host()
    hosts = [h for h in getattr(settings, "ALLOWED_HOSTS", []) if h not in ("*", "")]
    return "https", (hosts[0] if hosts else "localhost:8000")


def enviar_convite(
    *, user: User, request: HttpRequest | None = None, remetente: User | None = None
) -> bool:
    """Envia o convite. Devolve False sem e-mail cadastrado — conta existe, convite não sai."""
    if not user.email:
        return False

    protocolo, dominio = _dominio(request)
    contexto = {
        "nome": user.get_full_name() or user.email,
        "perfil": user.get_role_display(),
        "remetente": (remetente.get_full_name() or remetente.email) if remetente else "",
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
        "protocol": protocolo,
        "domain": dominio,
        "exige_mfa": user.exige_mfa,
        "publica": user.pode_publicar,
    }

    assunto = render_to_string("email/convite_assunto.txt", contexto).strip()
    mensagem = EmailMultiAlternatives(
        subject=assunto,
        body=render_to_string("email/convite.txt", contexto),
        to=[user.email],
    )
    mensagem.attach_alternative(render_to_string("email/convite.html", contexto), "text/html")
    mensagem.send()
    return True
