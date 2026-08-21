"""Atribuição de carteira de clientes.

A decisão que este módulo protege: **ausência de atribuição significa nenhum acesso, não
acesso total**. Um técnico recém-criado não vê nada até alguém dizer o que ele deve ver. O
inverso — o padrão permissivo — é como vazamentos acontecem em produto multiempresa.
"""

from __future__ import annotations

from django.db import transaction

from apps.clientes.models import Client
from apps.core.enums import AuditAction, UserRole
from apps.core.models import ClientAssignment, User
from apps.core.services import registrar_auditoria


class CarteiraNaoSeAplica(Exception):
    """Administrador vê toda a organização — dar-lhe carteira criaria uma falsa restrição."""


@transaction.atomic
def atribuir_cliente(*, user: User, client: Client, actor: User | None = None) -> ClientAssignment:
    if user.ve_toda_a_organizacao:
        raise CarteiraNaoSeAplica(
            f"{user} tem perfil {user.get_role_display()} e já vê toda a organização. "
            "Atribuir clientes aqui sugeriria uma restrição que não existe."
        )
    if user.tenant_id != client.tenant_id:
        raise ValueError("Usuário e cliente pertencem a organizações diferentes.")

    vinculo, criado = ClientAssignment.objects.get_or_create(
        user=user, client=client,
        defaults={"tenant_id": user.tenant_id, "created_by": actor},
    )
    if criado:
        registrar_auditoria(
            action=AuditAction.CREATE, entity=vinculo, actor=actor,
            new_value={"usuario": user.username, "cliente": client.legal_name},
            tenant_id=user.tenant_id,
        )
    return vinculo


@transaction.atomic
def remover_cliente(*, user: User, client: Client, actor: User | None = None) -> bool:
    """Tirar acesso é decisão registrada — nunca uma exclusão silenciosa."""
    vinculo = ClientAssignment.objects.filter(user=user, client=client).first()
    if vinculo is None:
        return False
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=vinculo, actor=actor,
        old_value={"usuario": user.username, "cliente": client.legal_name},
        new_value={"acesso": "removido"},
        tenant_id=user.tenant_id,
    )
    vinculo.delete()
    return True


@transaction.atomic
def definir_carteira(
    *, user: User, client_ids: list[int], actor: User | None = None
) -> frozenset[int]:
    """Substitui a carteira inteira. Devolve o conjunto final."""
    if user.ve_toda_a_organizacao:
        raise CarteiraNaoSeAplica(
            f"{user} vê toda a organização — não há carteira a definir."
        )
    permitidos = set(
        Client.sem_escopo.filter(tenant_id=user.tenant_id, pk__in=client_ids)
        .values_list("pk", flat=True)
    )
    atuais = set(
        ClientAssignment.objects.filter(user=user).values_list("client_id", flat=True)
    )
    for client_id in atuais - permitidos:
        ClientAssignment.objects.filter(user=user, client_id=client_id).delete()
    for client_id in permitidos - atuais:
        ClientAssignment.objects.create(
            tenant_id=user.tenant_id, user=user, client_id=client_id, created_by=actor
        )
    if atuais != permitidos:
        registrar_auditoria(
            action=AuditAction.UPDATE, entity=user, actor=actor,
            old_value={"carteira": sorted(atuais)},
            new_value={"carteira": sorted(permitidos)},
            tenant_id=user.tenant_id,
        )
    return frozenset(permitidos)


def carteira_de(user: User) -> frozenset[int] | None:
    return user.carteira()


def usuarios_sem_carteira(tenant_id: int) -> list[User]:
    """Quem tem perfil restrito e nenhum cliente — vê telas vazias e não sabe por quê.

    Existe para a tela de administração avisar. É o efeito colateral previsível do padrão
    seguro, e avisar é melhor que afrouxar o padrão.
    """
    return [
        u
        for u in User.objects.filter(tenant_id=tenant_id, is_active=True)
        .exclude(role=UserRole.ADMIN)
        .prefetch_related("assignments")
        if not u.assignments.exists()
    ]
