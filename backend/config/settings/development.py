from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
        "TEST": {
            "NAME": BASE_DIR / "test_db.sqlite3",
        },
    }
}

CORS_ALLOW_ALL_ORIGINS = True

# Serve built frontend in dev/test when available
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(  # noqa: F405
    "rest_framework.renderers.BrowsableAPIRenderer"
)

# Print emails to console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SITE_BASE_URL = "http://localhost:5174"

# Google OAuth
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")  # noqa: F405
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")  # noqa: F405
