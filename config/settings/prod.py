"""Produção e homologação no Render.

O host externo e a URL pública vêm do próprio Render, para que o ambiente funcione
sem configuração manual no primeiro deploy.
"""

import os

from .base import *  # noqa: F403

DEBUG = False

# O Render publica o hostname do serviço nesta variável
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = [".onrender.com"]

CSRF_TRUSTED_ORIGINS = [f"https://{h.lstrip('.')}" for h in ALLOWED_HOSTS]

PUBLIC_VERIFY_BASE_URL = os.environ.get(
    "PUBLIC_VERIFY_BASE_URL", f"https://{RENDER_HOST}" if RENDER_HOST else ""
)

# O Render encerra o TLS no proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}  # noqa: F405
