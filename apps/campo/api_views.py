from __future__ import annotations

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .armazenamento import ArquivoGrandeDemais, TipoNaoAceito, presign
from .auth import DeviceTokenAuthentication
from .models import SyncBatch
from .selectors import pacote_offline
from .services import PareamentoRecusado, parear_aparelho, sincronizar

DISPOSITIVO = [DeviceTokenAuthentication]


def _erro(http: int, code: str, message: str, detalhes=None) -> Response:  # noqa: ANN001
    corpo = {"error": {"code": code, "message": message}}
    if detalhes:
        corpo["error"]["details"] = detalhes
    return Response(corpo, status=http)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def pair(request: Request) -> Response:
    """Pareamento é ato da sessão web autenticada — nunca do próprio aparelho."""
    from .serializers import PareamentoSerializer

    entrada = PareamentoSerializer(data=request.data)
    if not entrada.is_valid():
        return _erro(400, "validation_error", "Dados de pareamento inválidos.", entrada.errors)
    try:
        aparelho, token = parear_aparelho(
            operator=request.user, **entrada.validated_data
        )
    except PareamentoRecusado as erro:
        return _erro(403, "forbidden", str(erro))
    return Response(
        {
            "device": str(aparelho.public_uuid),
            "label": aparelho.label,
            "token": token,  # aparece UMA vez; o banco guarda apenas o hash
            "expires_at": aparelho.expires_at,
            "scope": ["field.read", "field.sync"],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@authentication_classes(DISPOSITIVO)
@permission_classes([IsAuthenticated])
def inspections(request: Request) -> Response:
    """Pacote de dados para uso offline — inclui os enunciados da biblioteca."""
    return Response(pacote_offline(operator=request.user))


@api_view(["POST"])
@authentication_classes(DISPOSITIVO)
@permission_classes([IsAuthenticated])
def sync(request: Request) -> Response:
    from .serializers import LoteSerializer

    entrada = LoteSerializer(data=request.data)
    if not entrada.is_valid():
        return _erro(400, "validation_error", "Lote malformado.", entrada.errors)
    dados = entrada.validated_data
    resultado = sincronizar(
        device=request.auth,
        client_batch_uuid=str(dados["client_batch_uuid"]),
        records=dados["records"],
        device_reported_at=dados.get("device_reported_at"),
    )
    return Response(resultado.as_dict())


@api_view(["GET"])
@authentication_classes(DISPOSITIVO)
@permission_classes([IsAuthenticated])
def sync_state(request: Request, client_batch_uuid: str) -> Response:
    """Estado do lote — permite ao aparelho conferir sem reenviar."""
    lote = SyncBatch.objects.filter(client_batch_uuid=client_batch_uuid).first()
    if lote is None:
        return _erro(404, "not_found", "Lote não encontrado para esta credencial.")
    return Response(
        {
            **(lote.response or {}),
            "received_at": lote.received_at,
            "clock_skew_seconds": lote.clock_skew_seconds,
            "needs_review": lote.precisa_revisao,
        }
    )


@api_view(["POST"])
@authentication_classes(DISPOSITIVO)
@permission_classes([IsAuthenticated])
def photos_presign(request: Request) -> Response:
    """URL assinada para envio direto ao armazenamento. A aplicação não trafega bytes."""
    from .serializers import PresignSerializer

    entrada = PresignSerializer(data=request.data)
    if not entrada.is_valid():
        return _erro(400, "validation_error", "Pedido de envio inválido.", entrada.errors)
    dados = entrada.validated_data
    aparelho = request.auth
    try:
        assinado = presign(
            tenant_id=aparelho.tenant_id, device_id=aparelho.device_id,
            client_uuid=str(dados["client_uuid"]), content_type=dados["content_type"],
            bytes_=dados["bytes"],
        )
    except TipoNaoAceito as erro:
        return _erro(415, "unsupported_media_type", str(erro))
    except ArquivoGrandeDemais as erro:
        return _erro(413, "payload_too_large", str(erro))
    return Response(
        {
            "upload_url": assinado.upload_url,
            "file_key": assinado.file_key,
            "expires_in": assinado.expires_in,
            "max_bytes": assinado.max_bytes,
            "direct_upload": assinado.direto,
        }
    )
