"""Tests for serving Django static files (admin CSS) in production.

Django with DEBUG=False does not serve /static/ on its own, and every
request reaches Django through the Next.js middleware proxy, so nginx
never gets a chance to serve the files either. WhiteNoise makes Django
self-sufficient: the same process that renders the admin serves its
stylesheets, in every environment, with no web-server configuration.
"""
from django.conf import settings

SECURITY_MIDDLEWARE = "django.middleware.security.SecurityMiddleware"
WHITENOISE_MIDDLEWARE = "whitenoise.middleware.WhiteNoiseMiddleware"


class TestWhiteNoiseConfiguration:
    def test_whitenoise_sits_directly_after_security_middleware(self):
        # The position WhiteNoise documents: above everything that could
        # touch the response, below only SecurityMiddleware.
        middleware = settings.MIDDLEWARE
        assert WHITENOISE_MIDDLEWARE in middleware
        assert (
            middleware.index(WHITENOISE_MIDDLEWARE)
            == middleware.index(SECURITY_MIDDLEWARE) + 1
        )

    def test_finders_are_enabled_outside_production(self):
        # Serves app static dirs (django.contrib.admin's css) without a
        # collectstatic step, so dev and CI behave like production without
        # a build artifact. Production runs collectstatic in deploy and
        # does not set this.
        assert settings.WHITENOISE_USE_FINDERS is True


class TestStaticFileServing:
    def test_admin_stylesheet_is_served(self, client):
        response = client.get("/static/admin/css/base.css")

        assert response.status_code == 200
        content_type = response.headers["Content-Type"]
        assert content_type.startswith("text/css")

    def test_missing_static_file_is_a_404_not_the_spa_shell(self, client):
        # The frontend catch-all must not answer for /static/: HTML with a
        # 200 is worse than a 404 for a browser asking for a stylesheet.
        response = client.get("/static/does-not-exist.css")

        assert response.status_code == 404
