"""Serviços do núcleo. Única casa da regra de negócio deste app."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .enums import AuditAction, UserRole
from .models import AuditLog, ClientAssignment, Tenant, User
from .tenancy import require_tenant


class AlteracaoDeAcessoInvalida(Exception):
    """Operação que deixaria a organização sem administrador, ou o autor sem entrada."""


def registrar_auditoria(
    *,
    action: AuditAction | str,
    entity: Any = None,
    entity_table: str = "",
    entity_id: int | None = None,
    actor: User | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip: str | None = None,
    tenant_id: int | None = None,
) -> AuditLog:
    """Grava uma linha na trilha. Chamado por todo serviço que escreve."""
    if entity is not None:
        entity_table = entity_table or entity._meta.db_table
        entity_id = entity_id or entity.pk
    return AuditLog.objects.create(
        tenant_id=tenant_id or require_tenant(),
        actor=actor,
        action=action,
        entity_table=entity_table,
        entity_id=entity_id,
        old_value=old_value or {},
        new_value=new_value or {},
        ip=ip,
    )


@transaction.atomic
def criar_usuario(
    *,
    tenant: Tenant,
    email: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    actor: User | None = None,
) -> User:
    """Cria usuário aplicando a exigência de MFA por perfil.

    ATENÇÃO: usuário de perfil restrito nasce SEM carteira e, portanto, sem ver nada. É
    deliberado — o padrão permissivo é como vazamentos acontecem. Depois de criar, atribua
    clientes com `apps.core.carteira.atribuir_cliente`; a tela de usuários avisa quem
    está sem carteira.
    """
    user = User(
        tenant=tenant,
        username=email,
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    user.mfa_enabled = user.exige_mfa
    user.set_unusable_password()
    user.full_clean(exclude=["password"])
    user.save()
    registrar_auditoria(
        action=AuditAction.CREATE,
        entity=user,
        actor=actor,
        new_value={
            "email": email, "role": role,
            "carteira": "toda a organização" if user.ve_toda_a_organizacao else "vazia",
        },
        tenant_id=tenant.pk,
    )
    return user


@transaction.atomic
def criar_usuario_com_acesso(
    *,
    tenant: Tenant,
    email: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    client_ids: list[int] | None = None,
    actor: User | None = None,
) -> User:
    """Cria a conta E decide o que ela vê, na mesma transação.

    Por que juntos: separar os dois passos produz, no intervalo, uma conta que existe e não
    vê nada. Em produto multiempresa esse intervalo é onde o gestor esquece o segundo passo
    e o técnico passa a semana achando que o sistema está vazio.

    Perfil sem restrição de carteira ignora `client_ids` — dar-lhe carteira registraria uma
    limitação que não existe de fato.
    """
    from .carteira import definir_carteira  # import local: carteira depende deste módulo

    user = criar_usuario(
        tenant=tenant, email=email, role=role,
        first_name=first_name, last_name=last_name, actor=actor,
    )
    if not user.ve_toda_a_organizacao:
        definir_carteira(user=user, client_ids=list(client_ids or []), actor=actor)
    return user


def _outros_admins_ativos(user: User) -> bool:
    return (
        User.objects.filter(tenant_id=user.tenant_id, role=UserRole.ADMIN, is_active=True)
        .exclude(pk=user.pk)
        .exists()
    )


@transaction.atomic
def alterar_perfil(*, user: User, role: str, actor: User | None = None) -> User:
    """Troca o perfil. Muda o que a pessoa vê e o que ela pode assinar — nunca é rotina.

    Duas travas:
    - a organização não pode ficar sem administrador ativo;
    - promover a administrador APAGA a carteira, em vez de guardá-la. Carteira parada é
      acesso que volta sozinho num rebaixamento futuro, e acesso não deve ressuscitar.
    """
    anterior = user.role
    if anterior == role:
        return user
    if anterior == UserRole.ADMIN and not _outros_admins_ativos(user):
        raise AlteracaoDeAcessoInvalida(
            f"{user} é o único administrador ativo da organização. "
            "Promova outra pessoa antes de rebaixar esta conta."
        )

    user.role = role
    if user.exige_mfa:
        user.mfa_enabled = True
    user.save(update_fields=["role", "mfa_enabled"])

    carteira_apagada = 0
    if user.ve_toda_a_organizacao:
        carteira_apagada = ClientAssignment.objects.filter(user=user).count()
        ClientAssignment.objects.filter(user=user).delete()

    registrar_auditoria(
        action=AuditAction.UPDATE, entity=user, actor=actor,
        old_value={"role": anterior},
        new_value={"role": role, "carteira_apagada": carteira_apagada},
        tenant_id=user.tenant_id,
    )
    return user


@transaction.atomic
def definir_situacao(*, user: User, ativo: bool, actor: User | None = None) -> User:
    """Desativa ou reativa. Nunca exclui: a trilha de auditoria aponta para o usuário.

    Reativar não devolve carteira nenhuma — o acesso é reconcedido à mão, de propósito.
    """
    if user.is_active == ativo:
        return user
    if not ativo:
        if actor is not None and user.pk == actor.pk:
            raise AlteracaoDeAcessoInvalida(
                "Você não pode desativar a própria conta — ficaria sem como voltar."
            )
        if user.role == UserRole.ADMIN and not _outros_admins_ativos(user):
            raise AlteracaoDeAcessoInvalida(
                f"{user} é o único administrador ativo. Desativar deixaria a organização "
                "sem quem gerencie acesso."
            )

    user.is_active = ativo
    user.save(update_fields=["is_active"])
    registrar_auditoria(
        action=AuditAction.UPDATE, entity=user, actor=actor,
        old_value={"is_active": not ativo},
        new_value={"is_active": ativo},
        tenant_id=user.tenant_id,
    )
    return user
