from pathlib import Path

import environ

from config.observability import init_sentry

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env.read_env(BASE_DIR.parent / ".env", overrides=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")

init_sentry(
    dsn=env("SENTRY_DSN", default=""),
    environment=env("SENTRY_ENVIRONMENT", default="development"),
    release=env("SENTRY_RELEASE", default=None),
    traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=1.0),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "quotes",
    "accounts",
    "social",
    "assistant",
]

MIDDLEWARE = [
    "config.middleware.request_id.RequestIDMiddleware",
    "config.middleware.server_timing.ServerTimingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Runs on the response after SessionMiddleware has added its Set-Cookie
    # and Vary: Cookie, so we can strip them on anonymous public-cached
    # responses before the response leaves the process.
    "config.middleware.public_cache_strip.StripSessionFromPublicCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.language_middleware.LanguagePersistenceMiddleware",
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "config.logging_formatter.JSONLogFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGO_CACHE_DIR = BASE_DIR / "logo_cache"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CsrfExemptSessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Social write actions — limits are intentionally tight (5× more
        # stringent than typical defaults). See backend/social/throttles.py.
        "spond_write_minute": "4/min",
        "spond_write_hour": "24/hour",
        "spond_write_day": "80/day",
        "spond_like_minute": "12/min",
        "spond_like_hour": "120/hour",
        "spond_like_day": "600/day",
        "follow_write_minute": "6/min",
        "follow_write_hour": "20/hour",
        "follow_write_day": "60/day",
        "relation_write_minute": "8/min",
        "relation_write_hour": "20/hour",
        "profile_write_hour": "6/hour",
        "notif_write_minute": "24/min",
        # Social read actions.
        "social_anon": "60/min",
        "social_user": "300/min",
    },
}

BRAPI_API_KEY = env("BRAPI_API_KEY")
BRAPI_BASE_URL = "https://brapi.dev/api"

FMP_API_KEY = env("FMP_API_KEY", default="")
FMP_BASE_URL = "https://financialmodelingprep.com"

FRED_API_KEY = env("FRED_API_KEY", default="")
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

# Daily distinct-company lookup caps. Anonymous is scoped per client IP
# (see quotes.lookup_quota); unverified accounts per user; verified
# accounts are unlimited.
SPONDA_ANON_LOOKUPS_PER_DAY = env.int("SPONDA_ANON_LOOKUPS_PER_DAY", default=20)
SPONDA_UNVERIFIED_LOOKUPS_PER_DAY = env.int(
    "SPONDA_UNVERIFIED_LOOKUPS_PER_DAY", default=50
)

# Redis cache (production override can change LOCATION via env).
# max_connections sizes the pool for the home-page fanout (~60 in-flight
# requests on a fresh visit) so pool exhaustion does not become the bottleneck.
# Django's built-in RedisCache forwards leftover OPTIONS to redis.ConnectionPool.from_url,
# so max_connections must sit at the OPTIONS top level (the django-redis-style
# CONNECTION_POOL_KWARGS wrapper would leak the literal key down into AbstractConnection
# and raise TypeError at first cache.get).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "max_connections": 50,
        },
    }
}

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
# Periodic jobs run via systemd timers, not celery beat. See systemd/sponda-revisit-reminders.{service,timer}.
