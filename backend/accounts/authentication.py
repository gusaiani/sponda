from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF enforcement.

    Safe for same-origin API requests where the frontend and backend
    share the same domain (or use a dev proxy). CORS headers prevent
    cross-origin requests from other domains.
    """

    def enforce_csrf(self, request):
        # Skip CSRF check — handled by CORS instead
        return
