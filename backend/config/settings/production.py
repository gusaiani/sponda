from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS") + ["127.0.0.1", "localhost"]  # noqa: F405

DATABASES = {
    "default": env.db("DATABASE_URL"),  # noqa: F405
}
# Reuse Postgres connections across requests for up to 10 minutes. With
# the home-page fanout (~60 parallel API calls), opening a fresh TCP+auth
# connection per request is a meaningful slice of latency.
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

CSRF_TRUSTED_ORIGINS = [
    "https://sponda.capital",
    "https://www.sponda.capital",
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"  # noqa: F405

# Email via Resend SMTP (sponda.capital verified as the sending domain)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = env("RESEND_API_KEY")  # noqa: F405
DEFAULT_FROM_EMAIL = "Sponda <noreply@sponda.capital>"
SITE_BASE_URL = "https://sponda.capital"
FEEDBACK_EMAIL = env("FEEDBACK_EMAIL", default="gustavo@poe.ma")  # noqa: F405

# Google OAuth
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")  # noqa: F405
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")  # noqa: F405
