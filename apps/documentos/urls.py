from django.urls import path

from .views import (
    baixar_pdf,
    detalhe_documento,
    emitir,
    integridade_documento,
    lista_documentos,
    painel_bloqueios,
    previa,
    publicar_documento,
    verificacao_publica_html,
)

urlpatterns = [
    path("documentos/", lista_documentos, name="documentos"),
    path("documentos/emitir", emitir, name="emitir_documento"),
    path("documentos/<uuid:uuid>/", detalhe_documento, name="documento"),
    path("documentos/<uuid:uuid>/bloqueios", painel_bloqueios, name="bloqueios_documento"),
    path("documentos/<uuid:uuid>/previa", previa, name="previa_documento"),
    path("documentos/<uuid:uuid>/publicar", publicar_documento, name="publicar_documento"),
    path("documentos/<uuid:uuid>/pdf", baixar_pdf, name="pdf_documento"),
    path("documentos/<uuid:uuid>/integridade", integridade_documento, name="integridade_documento"),
    # Rota pública: curta de propósito — é digitada à mão quando o QR falha.
    path("d/<uuid:uuid>", verificacao_publica_html, name="verificacao_publica"),
]
