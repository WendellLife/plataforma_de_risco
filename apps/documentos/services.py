"""Serviços de emissão de documento.

Regra central do produto: publicação é um ato verificado. O verificador roda no
servidor, com as regras que o template exige, e o resultado é gravado — não é um
aviso de tela (Espec 01, item 7; Espec 04, item 5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.enums import AuditAction, UserRole
from apps.core.models import User
from apps.core.services import registrar_auditoria
from apps.core.tenancy import require_tenant
from motores.documento import Contexto, Trilha, build_context
from motores.documento import template as template_do_catalogo
from motores.verificador import Violacao

from .enums import ESTADOS_PUBLICAVEIS, DocumentStatus, SignatureStatus
from .models import Document, DocumentVersion, PublicationBlock
from .selectors import escopo_da_maquina


class PublicacaoBloqueada(Exception):
    """A publicação foi recusada pelo verificador. Carrega TODAS as violações."""

    def __init__(self, violacoes: list[Violacao]) -> None:
        self.violacoes = violacoes
        super().__init__(f"{len(violacoes)} bloqueio(s) impedem a publicação.")


class PermissaoDePublicacao(Exception):
    """Somente engenheiro publica peça de responsabilidade técnica (Espec 01, item 9)."""


@transaction.atomic
def criar_documento(*, machine, template_code: str, actor: User | None = None) -> Document:  # noqa: ANN001
    template = template_do_catalogo(template_code)
    doc = Document(
        tenant_id=require_tenant(),
        machine=machine,
        project=machine.project,
        template_code=template.codigo,
        title=f"{template.nome} — {machine.name}",
        number=_numero(machine, template.codigo),
        created_by=actor,
    )
    doc.full_clean(exclude=["number"])
    doc.save()
    registrar_auditoria(
        action=AuditAction.CREATE, entity=doc, actor=actor,
        new_value={"template": template.codigo, "maquina": machine.name},
    )
    return doc


def _numero(machine, template_code: str) -> str:  # noqa: ANN001
    projeto = machine.project.number if machine.project else "SEM-PROJ"
    sequencia = Document.objects.filter(machine=machine, template_code=template_code).count() + 1
    return f"{projeto}/{template_code}-{sequencia:03d}"


def montar(*, documento: Document) -> Contexto:
    """Contexto de renderização — mesma função usada na prévia e na publicação."""
    escopo = escopo_da_maquina(str(documento.machine.public_uuid))
    escopo["documento"] = {
        "numero": documento.number,
        "titulo": documento.title,
        "situacao": documento.get_status_display(),
        "uuid": str(documento.public_uuid),
        "versao": documento.current_version.number if documento.current_version else None,
        "emitido_em": timezone.localtime(),
    }
    return build_context(escopo=escopo, template=documento.template)


@transaction.atomic
def sincronizar_bloqueios(*, documento: Document, contexto: Contexto) -> int:
    """Grava as violações atuais e resolve as que deixaram de existir.

    Devolve o número de bloqueios abertos. Chamado na prévia e antes de publicar —
    é o que permite ao usuário sair, corrigir e voltar sem perder a lista.
    """
    agora = timezone.now()
    atuais = {(v.regra, v.mensagem): v for v in [*contexto.bloqueios, *contexto.avisos]}
    abertos = {
        (b.rule, b.message): b
        for b in documento.blocks.filter(resolved_at__isnull=True)
    }
    for chave, bloco in abertos.items():
        if chave not in atuais:
            bloco.resolved_at = agora
            bloco.save(update_fields=["resolved_at"])
    for chave, violacao in atuais.items():
        if chave in abertos:
            continue
        PublicationBlock.objects.create(
            tenant_id=require_tenant(),
            document=documento,
            rule=violacao.regra,
            severity=violacao.severidade,
            message=violacao.mensagem,
            entity=violacao.entidade,
            fix_path=violacao.caminho_correcao,
        )
    novo_status = (
        DocumentStatus.BLOCKED if contexto.bloqueios
        else DocumentStatus.READY if documento.status in ESTADOS_PUBLICAVEIS
        else documento.status
    )
    if documento.status in ESTADOS_PUBLICAVEIS and documento.status != novo_status:
        documento.status = novo_status
        documento.save(update_fields=["status", "updated_at"])
    return len(contexto.bloqueios)


def publicar(*, documento: Document, actor: User) -> DocumentVersion:
    """Publica uma nova versão. Recusa em bloco, com todas as violações de uma vez."""
    template = documento.template
    if template.exige_engenheiro and actor.role != UserRole.ENGINEER:
        registrar_auditoria(
            action=AuditAction.PERMISSION_DENIED, entity=documento, actor=actor,
            new_value={"motivo": "perfil não publica peça de responsabilidade técnica"},
        )
        raise PermissaoDePublicacao(
            f"{template.nome} é peça de responsabilidade técnica — somente engenheiro publica."
        )

    # A recusa precisa SOBREVIVER à chamada: é a lista que o usuário vai corrigir. Por
    # isso a verificação roda fora da transação — dentro dela, o raise desfaria tanto os
    # PublicationBlock recém-gravados quanto o status BLOCKED.
    contexto = montar(documento=documento)
    sincronizar_bloqueios(documento=documento, contexto=contexto)
    if contexto.bloqueios:
        raise PublicacaoBloqueada(contexto.bloqueios)

    with transaction.atomic():
        versao = _gravar_versao(documento=documento, contexto=contexto, actor=actor)
    # Fora da transação: o worker não pode ver uma versão ainda não confirmada.
    _agendar_composicao(versao)
    return versao


def _gravar_versao(*, documento: Document, contexto: Contexto, actor: User) -> DocumentVersion:
    template = documento.template
    payload = contexto.as_dict()
    versao = DocumentVersion.objects.create(
        tenant_id=require_tenant(),
        document=documento,
        number=documento.proximo_numero_de_versao,
        content_hash=_hash(payload),
        context_snapshot=_serializavel(payload),
        verification_snapshot=[
            {"regra": v.regra, "severidade": v.severidade, "mensagem": v.mensagem}
            for v in contexto.avisos
        ],
        method_versions=contexto.method_versions,
        signature_track=template.trilha,
        signature_status=(
            SignatureStatus.NONE if template.trilha is Trilha.SEM_ASSINATURA
            else SignatureStatus.PENDING
        ),
        published_at=timezone.now(),
        published_by=actor,
        created_by=actor,
    )
    anteriores = documento.versions.exclude(pk=versao.pk)
    documento.current_version = versao
    documento.status = DocumentStatus.PUBLISHED
    documento.save(update_fields=["current_version", "status", "updated_at"])
    registrar_auditoria(
        action=AuditAction.PUBLISH, entity=documento, actor=actor,
        new_value={
            "versao": versao.number, "hash": versao.content_hash,
            "trilha": template.trilha, "substitui": anteriores.count(),
            "avisos": len(contexto.avisos),
        },
    )
    return versao


def _agendar_composicao(versao: DocumentVersion) -> None:
    """Enfileira a composição do PDF; em dev roda em linha se o broker não responder."""
    from .tasks import compor_pdf

    try:
        compor_pdf.delay(versao.pk)
    except Exception:  # noqa: BLE001 - broker indisponível não pode derrubar a publicação
        pass


def _serializavel(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, default=str))


def _hash(payload: dict[str, Any]) -> str:
    corpo = json.dumps(_serializavel(payload), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(corpo.encode("utf-8")).hexdigest()
