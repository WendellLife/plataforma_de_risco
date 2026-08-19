import os

from celery import Celery

# Importado por config/__init__.py, portanto o PRIMEIRO a definir o padrão em
# qualquer processo. Padrão seguro é prod; dev vem do .env ou do manage.py.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("plataforma_de_risco")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
