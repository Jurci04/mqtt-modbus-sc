from pathlib import Path

from shared.settings import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent
settings = get_settings()


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated setting into a cleaned list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_database() -> dict[str, str]:
    """Build Django default database settings from shared app settings."""
    return {
        "ENGINE": settings.django_db_engine,
        "NAME": settings.django_db_name,
        "USER": settings.django_db_user,
        "PASSWORD": settings.django_db_password,
        "HOST": settings.django_db_host,
        "PORT": settings.django_db_port,
    }


SECRET_KEY = settings.django_secret_key
DEBUG = settings.django_debug
ALLOWED_HOSTS = _split_csv(settings.django_allowed_hosts)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backend.api",
    "backend.devices",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.config.wsgi.application"
ASGI_APPLICATION = "backend.config.asgi.application"

DATABASES = {"default": _default_database()}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
