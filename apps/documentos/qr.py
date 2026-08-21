"""QR de verificação — SVG embutido, sem binário e sem dependência de imagem.

Vive num módulo próprio porque a saída entra em template de impressão: gerar QR como PNG
exigiria arquivo temporário e caminho absoluto dentro do WeasyPrint. Como SVG em linha,
o QR viaja com o HTML e imprime igual em tela e em papel.
"""

from __future__ import annotations

import base64


def svg(dados: str, *, borda: int = 2) -> str:
    """SVG do QR como string. Devolve "" se a biblioteca não estiver instalada."""
    try:
        import qrcode
    except ImportError:  # ambiente sem a dependência: o documento imprime só a URL
        return ""
    codigo = qrcode.QRCode(border=borda, error_correction=qrcode.constants.ERROR_CORRECT_M)
    codigo.add_data(dados)
    codigo.make(fit=True)
    matriz = codigo.get_matrix()
    lado = len(matriz)
    modulos = "".join(
        f'<rect x="{x}" y="{y}" width="1" height="1"/>'
        for y, linha in enumerate(matriz)
        for x, escuro in enumerate(linha)
        if escuro
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado} {lado}" '
        f'shape-rendering="crispEdges"><rect width="{lado}" height="{lado}" fill="#fff"/>'
        f'<g fill="#000">{modulos}</g></svg>'
    )


def data_uri(dados: str) -> str:
    """O mesmo QR como data URI — para usar em src de <img> no template de impressão."""
    marcacao = svg(dados)
    if not marcacao:
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(marcacao.encode("utf-8")).decode()
