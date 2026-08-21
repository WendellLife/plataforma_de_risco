"""Verificação pública de integridade (CA-06).

A única superfície do produto sem autenticação. O que ela existe para responder é uma
pergunta de terceiro — fiscal, auditor, cliente do cliente: *este papel na minha mão foi
mesmo emitido, e continua igual?*

Três limites que definem esta camada:

1. **Confirma, não expõe.** Devolve identidade do documento, hash, revisão, data e
   responsável técnico. NÃO devolve conteúdo técnico, dado pessoal, CPF, endereço, nem o
   risco apreciado. Quem precisa do conteúdo pede ao contratante.
2. **Só o publicado existe aqui.** Minuta não tem verificação pública — não há o que
   confirmar sobre documento que ninguém emitiu.
3. **Não enumera.** O identificador é `public_uuid` (128 bits, não sequencial). Documento
   inexistente e documento de outro tenant devolvem a mesma resposta: não encontrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Document, DocumentVersion


@dataclass(frozen=True, slots=True)
class Comprovacao:
    encontrado: bool
    numero: str = ""
    template: str = ""
    template_nome: str = ""
    revisao: str = ""
    versao: int | None = None
    publicado_em: Any = None
    content_hash: str = ""
    responsavel: str = ""
    registro: str = ""
    contratante: str = ""
    maquina: str = ""
    trilha: str = ""
    assinatura: str = ""
    metodo: dict[str, str] = field(default_factory=dict)
    substituida: bool = False

    def as_dict(self) -> dict[str, Any]:
        if not self.encontrado:
            return {"found": False}
        return {
            "found": True,
            "document_number": self.numero,
            "template": self.template,
            "template_name": self.template_nome,
            "revision": self.revisao,
            "version": self.versao,
            "published_at": self.publicado_em,
            "content_hash": self.content_hash,
            "engineer": self.responsavel,
            "engineer_registration": self.registro,
            "contracting_party": self.contratante,
            "machine": self.maquina,
            "signature_track": self.trilha,
            "signature_status": self.assinatura,
            "method_versions": self.metodo,
            "superseded": self.substituida,
        }


def comprovar(public_uuid: str, *, versao_numero: int | None = None) -> Comprovacao:
    """Sem escopo de tenant DE PROPÓSITO: quem consulta não tem credencial nenhuma."""
    documento = (
        Document.sem_escopo.select_related(
            "current_version", "machine", "machine__client", "project", "project__engineer"
        )
        .filter(public_uuid=public_uuid)
        .first()
    )
    if documento is None or documento.current_version_id is None:
        return Comprovacao(encontrado=False)

    versao = documento.current_version
    substituida = False
    if versao_numero is not None and versao_numero != versao.number:
        anterior = DocumentVersion.sem_escopo.filter(
            document=documento, number=versao_numero
        ).first()
        if anterior is None:
            return Comprovacao(encontrado=False)
        versao, substituida = anterior, True

    engenheiro = getattr(documento.project, "engineer", None)
    template = documento.template
    return Comprovacao(
        encontrado=True,
        numero=documento.number,
        template=template.codigo,
        template_nome=template.nome,
        revisao=f"{template.chave_legada} rev. {template.revisao}",
        versao=versao.number,
        publicado_em=versao.published_at,
        content_hash=versao.content_hash,
        responsavel=getattr(engenheiro, "name", ""),
        registro=getattr(engenheiro, "registro_completo", "") or "",
        contratante=documento.machine.client.legal_name,
        maquina=documento.machine.name,
        trilha=versao.signature_track,
        assinatura=versao.get_signature_status_display(),
        metodo=versao.method_versions or {},
        substituida=substituida,
    )


def url_de_verificacao(documento: Document, base: str = "") -> str:
    """URL impressa no QR. Curta de propósito: é digitada à mão quando o QR falha."""
    return f"{base.rstrip('/')}/d/{documento.public_uuid}"
