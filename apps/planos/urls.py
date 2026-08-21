from django.urls import path

from .views import (
    cancelar,
    concluir,
    evidenciar,
    gerar_acoes,
    iniciar,
    lista_de_acoes,
    painel_de_adequacao,
    plano_da_maquina,
    repactuar,
)

urlpatterns = [
    path("acoes/", lista_de_acoes, name="acoes"),
    path("maquinas/<uuid:uuid>/plano/", plano_da_maquina, name="plano_maquina"),
    path("maquinas/<uuid:uuid>/plano/gerar", gerar_acoes, name="gerar_acoes"),
    path("clientes/<uuid:uuid>/adequacao/", painel_de_adequacao, name="adequacao_cliente"),
    path("acoes/<uuid:uuid>/iniciar", iniciar, name="iniciar_acao"),
    path("acoes/<uuid:uuid>/concluir", concluir, name="concluir_acao"),
    path("acoes/<uuid:uuid>/evidencia", evidenciar, name="evidenciar_acao"),
    path("acoes/<uuid:uuid>/prazo", repactuar, name="repactuar_prazo"),
    path("acoes/<uuid:uuid>/cancelar", cancelar, name="cancelar_acao"),
]
