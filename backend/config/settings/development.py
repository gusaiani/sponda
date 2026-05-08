from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": env.db("DEV_DATABASE_URL", default="postgres:///sponda"),  # noqa: F405
}

CORS_ALLOW_ALL_ORIGINS = True

# Serve built frontend in dev/test when available
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(  # noqa: F405
    "rest_framework.renderers.BrowsableAPIRenderer"
)

# Email: send via Resend when RESEND_API_KEY is configured; fall back to
# the console backend (prints messages to stdout) so contributors without
# the key can still develop. Mirrors production's SMTP config — same
# host, port, credentials, and From address.
_RESEND_API_KEY = env("RESEND_API_KEY", default="")  # noqa: F405
if _RESEND_API_KEY:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True
    EMAIL_HOST_USER = "resend"
    EMAIL_HOST_PASSWORD = _RESEND_API_KEY
    DEFAULT_FROM_EMAIL = "Sponda <noreply@sponda.capital>"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Where verification / reset / share links in outbound emails point to.
# Next.js dev server listens on 3000; this URL must match the browser
# the user clicks the link in.
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:3000")  # noqa: F405

FEEDBACK_EMAIL = env("FEEDBACK_EMAIL", default="gustavo@poe.ma")  # noqa: F405

# Google OAuth
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")  # noqa: F405
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")  # noqa: F405

# Use in-memory cache for local dev (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
