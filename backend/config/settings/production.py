from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS") + ["127.0.0.1", "localhost"]  # noqa: F405

DATABASES = {
    "default": env.db("DATABASE_URL"),  # noqa: F405
}

CSRF_TRUSTED_ORIGINS = [
    "https://sponda.poe.ma",
    "https://sponda.capital",
    "https://www.sponda.capital",
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"  # noqa: F405

# Email via Resend SMTP (reusing existing poe.ma domain verification)
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
