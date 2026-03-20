import re
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path, re_path

# Matches ticker-style URL paths like /PETR4, /VALE3, /BBAS3
# Also matches sub-paths like /PETR4/graficos, /PETR4/comparar
_TICKER_RE = re.compile(r"^([A-Za-z]{4}\d{1,2})(?:/(?:graficos|comparar))?$")

_BASE_URL = "https://sponda.com.br"


def _inject_og_tags(html: str, ticker: str) -> str:
    """Replace default OG meta tags with ticker-specific ones for social crawlers."""
    og_title = f"{ticker} — Sponda"
    og_desc = f"Indicadores fundamentalistas de {ticker}: P/L ajustado pela inflação, P/FCL, PEG, CAGR e alavancagem."
    og_url = f"{_BASE_URL}/{ticker}"
    og_image = f"{_BASE_URL}/api/og/{ticker}.png"
    page_title = f"{ticker} — Sponda"

    replacements = [
        ('property="og:title"', og_title),
        ('property="og:description"', og_desc),
        ('property="og:url"', og_url),
        ('name="twitter:title"', page_title),
        ('name="twitter:description"', og_desc),
    ]
    for attr, content in replacements:
        html = re.sub(
            rf'<meta\s+{re.escape(attr)}\s+content="[^"]*"\s*/?>',
            f'<meta {attr} content="{content}" />',
            html,
        )

    # Inject og:image (add after og:url)
    og_image_tag = f'<meta property="og:image" content="{og_image}" />'
    twitter_image_tag = f'<meta name="twitter:image" content="{og_image}" />'
    twitter_card_large = '<meta name="twitter:card" content="summary_large_image" />'
    html = html.replace(
        '<meta name="twitter:card" content="summary" />',
        twitter_card_large,
    )
    html = html.replace("</head>", f"    {og_image_tag}\n    {twitter_image_tag}\n  </head>")

    # Update <title>
    html = re.sub(r"<title>[^<]*</title>", f"<title>{page_title}</title>", html)

    # Update meta description
    html = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
        f'<meta name="description" content="{og_desc}" />',
        html,
    )

    # Update canonical
    html = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
        f'<link rel="canonical" href="{og_url}" />',
        html,
    )

    return html


def _serve_frontend(request, filepath=""):
    """Serve the built frontend SPA. Falls back to index.html for client-side routing.

    For ticker pages (e.g. /PETR4), injects OG meta tags server-side so social
    media crawlers see the right title, description, and image.
    """
    dist_dir = getattr(settings, "FRONTEND_DIST_DIR", None)
    if not dist_dir:
        raise Http404

    dist_dir = Path(dist_dir)
    if filepath:
        file_path = dist_dir / filepath
        if file_path.is_file():
            return FileResponse(open(file_path, "rb"))

    index = dist_dir / "index.html"
    if not index.is_file():
        raise Http404

    # Check if this is a ticker page that needs OG injection
    ticker_match = _TICKER_RE.match(filepath) if filepath else None
    if ticker_match:
        html = index.read_text()
        html = _inject_og_tags(html, ticker_match.group(1).upper())
        return HttpResponse(html, content_type="text/html")

    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("quotes.urls")),
    path("api/auth/", include("accounts.urls")),
    re_path(r"^(?P<filepath>assets/.*)$", _serve_frontend),
    re_path(r"^(?!api/|admin/)(?P<filepath>.*)$", _serve_frontend),
]
