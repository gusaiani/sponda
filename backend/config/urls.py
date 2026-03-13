from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def _serve_frontend(request, filepath=""):
    """Serve the built frontend SPA. Falls back to index.html for client-side routing."""
    dist_dir = getattr(settings, "FRONTEND_DIST_DIR", None)
    if not dist_dir:
        raise Http404

    dist_dir = Path(dist_dir)
    if filepath:
        file_path = dist_dir / filepath
        if file_path.is_file():
            return FileResponse(open(file_path, "rb"))

    index = dist_dir / "index.html"
    if index.is_file():
        return FileResponse(open(index, "rb"), content_type="text/html")

    raise Http404


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("quotes.urls")),
    path("api/auth/", include("accounts.urls")),
    re_path(r"^(?P<filepath>assets/.*)$", _serve_frontend),
    re_path(r"^(?!api/|admin/)(?P<filepath>.*)$", _serve_frontend),
]
