from .models import PageView

# Paths to skip — static assets, API calls, admin panel
SKIP_PREFIXES = ("/api/", "/admin/", "/assets/", "/static/", "/favicon")


class PageViewTrackingMiddleware:
    """Records page views for analytics. Lightweight: skips API/static requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only track successful GET requests to frontend pages
        if request.method != "GET":
            return response

        if response.status_code != 200:
            return response

        path = request.path
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return response

        # Skip requests for files with extensions (images, JS, CSS, etc.)
        last_segment = path.rstrip("/").rsplit("/", 1)[-1]
        if "." in last_segment:
            return response

        ip_address = self._get_client_ip(request)
        ip_hash = PageView.hash_ip(ip_address)

        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ""

        PageView.objects.create(
            path=path,
            ip_hash=ip_hash,
            user=user,
            session_key=session_key,
        )

        return response

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP, respecting X-Forwarded-For from reverse proxy."""
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")
