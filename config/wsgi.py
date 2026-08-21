import os

from django.core.wsgi import get_wsgi_application

# Servido por gunicorn — só roda em ambiente publicado. O padrão seguro é prod:
# sem a variável definida, o app sobe fechado em vez de abrir com DEBUG ligado.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()
