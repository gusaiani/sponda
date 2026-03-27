import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path, re_path

# Matches ticker-style URL paths like /PETR4, /VALE3, /BBAS3
# Also matches sub-paths like /PETR4/graficos, /PETR4/comparar, /PETR4/fundamentos
_TICKER_RE = re.compile(r"^([A-Za-z]{4}\d{1,2})(?:/(?:graficos|comparar|fundamentos))?$")
# Frontend SPA routes that should NOT be treated as static file paths
_SPA_ROUTES = {"login", "signup", "forgot-password", "reset-password", "account", "shared"}

_BASE_URL = "https://sponda.capital"


_TAB_LABELS = {
    "": "Indicadores",
    "graficos": "Gráficos",
    "fundamentos": "Fundamentos",
    "comparar": "Comparar",
}


def _inject_og_tags(html: str, ticker: str, path: str = "") -> str:
    """Replace default OG meta tags with ticker-specific ones for social crawlers."""
    from quotes.models import Ticker as TickerModel
    from quotes.views import format_display_name

    ticker_obj = (
        TickerModel.objects.filter(symbol=ticker)
        .values("name", "display_name", "sector")
        .first()
    )
    company_name = (ticker_obj["display_name"] or format_display_name(ticker_obj["name"])) if ticker_obj else ""
    sector = ticker_obj["sector"] if ticker_obj else ""

    if company_name:
        page_title = f"{company_name} ({ticker}) — Indicadores Fundamentalistas | Sponda"
        og_title = f"{company_name} ({ticker}) — Sponda"
        og_desc = (
            f"Indicadores fundamentalistas de {company_name} ({ticker}): "
            f"P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. "
            f"Dados atualizados."
        )
    else:
        page_title = f"{ticker} — Sponda"
        og_title = page_title
        og_desc = (
            f"Indicadores fundamentalistas de {ticker}: "
            f"P/L ajustado pela inflação, P/FCL, PEG, CAGR e alavancagem."
        )

    full_path = f"{ticker}/{path}" if path else ticker
    og_url = f"{_BASE_URL}/{full_path}"
    og_image = f"{_BASE_URL}/og/{ticker}.png"

    replacements = [
        ('property="og:title"', og_title),
        ('property="og:description"', og_desc),
        ('property="og:url"', og_url),
        ('property="og:image"', og_image),
        ('name="twitter:title"', page_title),
        ('name="twitter:description"', og_desc),
        ('name="twitter:image"', og_image),
        ('name="twitter:card"', "summary_large_image"),
    ]
    for attr, content in replacements:
        html = re.sub(
            rf'<meta\s+{re.escape(attr)}\s+content="[^"]*"\s*/?>',
            f'<meta {attr} content="{content}" />',
            html,
        )

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

    # Inject ticker-specific JSON-LD structured data
    display_name = company_name or ticker
    tab_label = _TAB_LABELS.get(path, "Indicadores")

    dataset_schema = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Indicadores Fundamentalistas de {display_name} ({ticker})",
        "description": og_desc,
        "url": og_url,
        "keywords": [
            ticker, display_name, "PE10", "PFCF10", "PEG", "CAGR",
            "análise fundamentalista", "ações brasileiras", "B3",
        ],
        "creator": {
            "@type": "Organization",
            "name": "Sponda",
            "url": _BASE_URL,
        },
        "inLanguage": "pt-BR",
        "variableMeasured": [
            "P/L ajustado pela inflação (PE10)",
            "P/FCL ajustado pela inflação (PFCF10)",
            "PEG (Price/Earnings to Growth)",
            "CAGR do lucro líquido",
            "Alavancagem (Dívida/PL)",
        ],
    }
    if sector:
        dataset_schema["about"] = {"@type": "Thing", "name": sector}

    breadcrumb_items = [
        {"@type": "ListItem", "position": 1, "name": "Sponda", "item": _BASE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": ticker, "item": f"{_BASE_URL}/{ticker}"},
    ]
    if path:
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": 3,
            "name": tab_label,
            "item": og_url,
        })

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_items,
    }

    json_ld = (
        f'<script type="application/ld+json">\n'
        f'{json.dumps(dataset_schema, ensure_ascii=False, indent=2)}\n'
        f'</script>\n'
        f'<script type="application/ld+json">\n'
        f'{json.dumps(breadcrumb_schema, ensure_ascii=False, indent=2)}\n'
        f'</script>\n'
    )
    html = html.replace("</head>", f"    {json_ld}  </head>")

    # Inject meaningful content into <noscript> so crawlers see real text
    # (prevents Google from classifying the page as a Soft 404)
    sector_line = f"<p>Setor: {sector}</p>" if sector else ""
    noscript_content = (
        f"<noscript>\n"
        f"      <h1>{display_name} ({ticker}) — Indicadores Fundamentalistas</h1>\n"
        f"      <p>{og_desc}</p>\n"
        f"      {sector_line}\n"
        f"      <p>Indicadores disponíveis: PE10 (P/L ajustado pela inflação), "
        f"P/FCL10, PEG, CAGR do lucro e do fluxo de caixa, "
        f"Dívida/PL, Passivo/PL e mais.</p>\n"
        f'      <p><a href="{_BASE_URL}">Voltar para a página inicial do Sponda</a></p>\n'
        f"    </noscript>"
    )
    html = re.sub(
        r"<noscript>.*?</noscript>",
        noscript_content,
        html,
        flags=re.DOTALL,
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
        ticker = ticker_match.group(1).upper()
        # Extract sub-path (e.g. "graficos", "fundamentos") if present
        sub_path = filepath.split("/", 1)[1] if "/" in filepath else ""
        html = _inject_og_tags(html, ticker, sub_path)
        return HttpResponse(html, content_type="text/html")

    return FileResponse(open(index, "rb"), content_type="text/html")


def _serve_sitemap(request):
    """Serve sitemap.xml at the root URL by proxying to the API endpoint."""
    from quotes.views import SitemapView

    return SitemapView.as_view()(request)


def _serve_og_image(request, filename):
    """Serve OG images from disk cache, falling back to dynamic generation."""
    from quotes.views import OGImageView

    og_dir = Path(settings.BASE_DIR).parent / "og_images"
    cached = og_dir / filename
    if cached.is_file():
        return FileResponse(open(cached, "rb"), content_type="image/png")

    # Fall back to dynamic generation
    ticker = filename.removesuffix(".png") if filename != "home.png" else None
    return OGImageView.as_view()(request, ticker=ticker)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", _serve_sitemap, name="sitemap-root"),
    path("og/<str:filename>", _serve_og_image, name="og-image"),
    path("api/", include("quotes.urls")),
    path("api/auth/", include("accounts.urls")),
    re_path(r"^(?P<filepath>assets/.*)$", _serve_frontend),
    re_path(r"^(?!api/|admin/)(?P<filepath>.*)$", _serve_frontend),
]
