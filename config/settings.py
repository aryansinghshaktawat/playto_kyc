import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================
# SECURITY
# ======================

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-secret-key")

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

# For Render and testing set to wildcard. In production restrict this.
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")


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
    "EXCEPTION_HANDLER": "kyc.exceptions.custom_exception_handler",
    # For testing and to enable the browsable API POST button, allow any.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
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
