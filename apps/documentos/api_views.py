from __future__ import annotations

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .verificacao import comprovar


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def verificacao_publica(request: Request, public_uuid: str) -> Response:
    """A única rota sem autenticação. Confirma integridade sem expor conteúdo técnico."""
    versao = request.query_params.get("version")
    comprovacao = comprovar(
        str(public_uuid), versao_numero=int(versao) if versao and versao.isdigit() else None
    )
    if not comprovacao.encontrado:
        return Response(
            {"error": {"code": "not_found", "message": "Documento não encontrado."}}, status=404
        )
    return Response(comprovacao.as_dict())
