import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOGIN_REDIRECT_URL = "/api/v1/kyc/"

# ======================
# SECURITY
# ======================

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "2j#2v6q!z9v$4!4e1x@8k0x!5s@r9n#7m^q1d%w3y*8u0k!m@p",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

# For Render and testing set to wildcard. In production restrict this.
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


# ======================
# APPLICATIONS
# ======================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "kyc",
]


# ======================
# REST FRAMEWORK
# ======================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}



# ======================
# LOGGING (VERY IMPORTANT FOR DEBUGGING)
# ======================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "kyc": {
            "handlers": ["console"],
            "level": os.environ.get("KYC_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


# ======================
# MIDDLEWARE
# ======================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # IMPORTANT for static files in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ======================
# URL / WSGI
# ======================

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"


# ======================
# DATABASE
# ======================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ======================
# PASSWORD VALIDATION
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ======================
# INTERNATIONALIZATION
# ======================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ======================
# STATIC & MEDIA (CRITICAL)
# ======================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise storage for compressed static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# NOTE for Render/production:
# Local filesystem uploads are ephemeral on many PaaS providers.
# Move MEDIA storage to cloud object storage (S3/R2/GCS) for durability.


# ======================
# SECURITY (PRODUCTION)
# ======================

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)

SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", not DEBUG)


# ======================
# DEFAULT PK
# ======================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # you can keep empty
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
