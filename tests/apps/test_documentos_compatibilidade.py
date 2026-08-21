"""Regressões de compatibilidade da camada de documentos."""


def test_modulo_de_armazenamento_importa_no_django_suportado() -> None:
    from apps.documentos import armazenamento

    assert armazenamento.ALIAS == "documentos"
