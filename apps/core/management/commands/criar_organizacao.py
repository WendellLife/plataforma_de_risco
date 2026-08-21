"""Cria uma organização real e o primeiro administrador dela.

Existe porque `createsuperuser` resolve o problema errado: ele cria uma conta sem
organização, e toda tela do produto filtra por organização. O superusuário sem tenant
entra e não encontra nada — nem consegue criar o primeiro usuário, porque a criação herda
a organização de quem está criando.

    python manage.py criar_organizacao \\
        --razao-social "Life Laboral Consultoria" \\
        --cnpj 12345678000199 \\
        --admin admin@lifelaboral.com.br \\
        --nome "Wendell" --sobrenome "Silva"

Não define senha: o administrador recebe o convite e cria a própria, como qualquer outro
usuário. Nenhum caminho do sistema deixa alguém sabendo a senha de outra pessoa.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.convites import enviar_convite
from apps.core.enums import Plan, UserRole
from apps.core.models import Tenant, User
from apps.core.services import criar_usuario_com_acesso


class Command(BaseCommand):
    help = "Cria uma organização e o primeiro administrador, com convite por e-mail."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--razao-social", required=True)
        parser.add_argument("--cnpj", required=True, help="somente dígitos")
        parser.add_argument("--admin", required=True, help="e-mail do primeiro administrador")
        parser.add_argument("--nome", default="")
        parser.add_argument("--sobrenome", default="")
        parser.add_argument(
            "--plano", default=Plan.PILOT, choices=[v for v, _ in Plan.choices]
        )
        parser.add_argument(
            "--sem-convite",
            action="store_true",
            help="cria sem enviar e-mail; use quando o SMTP ainda não está configurado",
        )

    @transaction.atomic
    def handle(self, *args: Any, **opcoes: Any) -> None:
        cnpj = "".join(c for c in opcoes["cnpj"] if c.isdigit())
        if len(cnpj) != 14:
            raise CommandError("CNPJ precisa ter 14 dígitos.")
        if Tenant.objects.filter(tax_id=cnpj).exists():
            raise CommandError(f"Já existe organização com o CNPJ {cnpj}.")

        email = opcoes["admin"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise CommandError(f"Já existe conta com o e-mail {email}.")

        tenant = Tenant.objects.create(
            legal_name=opcoes["razao_social"], tax_id=cnpj, plan=opcoes["plano"]
        )
        admin = criar_usuario_com_acesso(
            tenant=tenant,
            email=email,
            role=UserRole.ADMIN,
            first_name=opcoes["nome"],
            last_name=opcoes["sobrenome"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Organização '{tenant.legal_name}' criada · administrador {admin.email}"
            )
        )
        if opcoes["sem_convite"]:
            self.stdout.write(
                "Convite não enviado (--sem-convite). Use 'Esqueci minha senha' na tela de "
                "login para receber o link quando o SMTP estiver configurado."
            )
            return
        if enviar_convite(user=admin):
            self.stdout.write(
                "Convite enviado. Sem SMTP configurado o e-mail sai no log do servidor — "
                "o link dele funciona igual."
            )
        else:
            self.stdout.write(self.style.WARNING("Convite não pôde ser enviado."))
