from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# O manifesto de estáticos exige collectstatic; em desenvolvimento e em teste não há
# manifesto e qualquer página com {% static %} quebraria. Produção mantém o de base.
STORAGES = {                      # noqa: F405
    **STORAGES,                   # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
