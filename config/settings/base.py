"""Configuração comum a todos os ambientes."""

from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "insegura-apenas-para-dev")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_htmx",
    "apps.core",
    "apps.clientes",
    "apps.ativos",
    "apps.checklists",
    "apps.risco",
    "apps.documentos",
    "apps.campo",
    "apps.planos",
    "apps.lotes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context.shell",
                "apps.core.context_marca.marca",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", "postgres://risco:risco@db:5432/risco"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# Armazenamento do artefato publicado (Sprint 7).
# O alias "documentos" é a ÚNICA porta usada por apps/documentos/armazenamento.py.
# Sem DOCUMENTS_BUCKET o alias cai em disco local — bom para dev, nunca para produção.
DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "")
DOCUMENTS_BUCKET_REGION = os.environ.get("DOCUMENTS_BUCKET_REGION", "us-east-1")
DOCUMENTS_BUCKET_ENDPOINT = os.environ.get("DOCUMENTS_BUCKET_ENDPOINT", "")  # S3-compatível
DOCUMENTS_URL_TTL = int(os.environ.get("DOCUMENTS_URL_TTL", "300"))  # segundos

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "documentos": (
        {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": DOCUMENTS_BUCKET,
                "region_name": DOCUMENTS_BUCKET_REGION,
                "endpoint_url": DOCUMENTS_BUCKET_ENDPOINT or None,
                "default_acl": "private",
                "querystring_auth": True,        # URL de leitura sempre assinada
                "querystring_expire": DOCUMENTS_URL_TTL,
                "file_overwrite": False,         # prova publicada não é sobrescrita
                "signature_version": "s3v4",
                "addressing_style": "virtual",
            },
        }
        if DOCUMENTS_BUCKET
        else {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(MEDIA_ROOT), "base_url": MEDIA_URL},
        }
    ),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Entrada e saída. Sem LOGIN_URL o Django manda para /accounts/login/, que não existe.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "painel"
LOGOUT_REDIRECT_URL = "login"

# E-mail. Sem SMTP configurado, imprime no console — nunca falha em silêncio nem
# finge ter enviado. O remetente carrega a marca da plataforma.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "Life Laboral <nao-responda@lifelaboral.com.br>"
)
PLATFORM_NAME = "Life Laboral"
PLATFORM_SUPPORT_EMAIL = os.environ.get("PLATFORM_SUPPORT_EMAIL", "suporte@lifelaboral.com.br")

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CELERY_TASK_ROUTES = {
    "apps.documentos.tasks.*": {"queue": "documentos"},
    "apps.lotes.tasks.*": {"queue": "lotes"},
    "apps.planos.tasks.*": {"queue": "planos"},
    "apps.campo.tasks.*": {"queue": "sincronizacao"},
    "apps.ativos.tasks.*": {"queue": "midia"},
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "apps.campo.auth.DeviceTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
}

# Campo e sincronização (Sprint 8). O aparelho envia a foto DIRETO ao armazenamento.
FIELD_PHOTO_MAX_BYTES = int(os.environ.get("FIELD_PHOTO_MAX_BYTES", "12000000"))
FIELD_UPLOAD_TTL = int(os.environ.get("FIELD_UPLOAD_TTL", "900"))
FIELD_TOKEN_DAYS = int(os.environ.get("FIELD_TOKEN_DAYS", "30"))

# Assinatura de documento — ver Espec 06, AD-11
SIGNING_MODE = os.environ.get("SIGNING_MODE", "simple")          # simple | qualified
SIGNING_PROVIDER = os.environ.get("SIGNING_PROVIDER", "cloud_a3")  # cloud_a3 | ecnpj_hsm
ICP_CERT_REF = os.environ.get("ICP_CERT_REF", "")
TIMESTAMP_AUTHORITY_URL = os.environ.get("TIMESTAMP_AUTHORITY_URL", "")
PUBLIC_VERIFY_BASE_URL = os.environ.get("PUBLIC_VERIFY_BASE_URL", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"format": '{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
