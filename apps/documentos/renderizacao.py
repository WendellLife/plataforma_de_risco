"""Composição do PDF. Única casa do WeasyPrint.

O HTML de impressão é o MESMO que a prévia em tela — não existe segundo template
para PDF. O que muda é apenas o meio de saída (Espec 03, item 4).
"""

from __future__ import annotations

from django.conf import settings
from django.template.loader import render_to_string

CAMINHO_TEMPLATE = "documentos/{codigo}/corpo.html"


def html_do_documento(*, documento, contexto, request=None) -> str:  # noqa: ANN001
    from motores.marca import Superficie, resolver

    from .qr import svg as qr_svg
    from .verificacao import url_de_verificacao

    base = getattr(settings, "PUBLIC_VERIFY_BASE_URL", "")
    # Minuta não tem verificação pública: não há o que confirmar sobre o que não foi emitido.
    url_verificacao = (
        url_de_verificacao(documento, base) if documento.current_version_id else ""
    )
    # Documento é SEMPRE co-marca: logo do contratante no cabeçalho, emissor técnico no
    # rodapé. O emissor não pode desaparecer da peça que ele assina.
    cliente = documento.machine.client
    marca = resolver(
        superficie=Superficie.DOCUMENTO,
        plataforma="Life Laboral",
        cliente=cliente.marca_dict if cliente.tem_marca_propria else None,
    )
    dados = contexto.as_dict()
    dados.update({
        "marca": marca,
        "documento": documento,
        "maquina": documento.machine,
        "base_url": base,
        "url_verificacao": url_verificacao,
        "qr_verificacao": qr_svg(url_verificacao) if url_verificacao else "",
        "modo_impressao": request is None,
    })
    return render_to_string(
        CAMINHO_TEMPLATE.format(codigo=documento.template_code), dados, request=request
    )


def pdf_do_html(html: str, *, base_url: str) -> tuple[bytes, int]:
    """Devolve (bytes do PDF, número de páginas)."""
    from weasyprint import HTML  # import tardio: só o worker de documentos precisa

    documento = HTML(string=html, base_url=base_url).render()
    return documento.write_pdf(), len(documento.pages)
