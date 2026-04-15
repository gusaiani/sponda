import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path, re_path

# Locales mirrored from frontend/src/lib/i18n-config.ts::SUPPORTED_LOCALES.
_LOCALES = ("pt", "en", "es", "zh", "fr", "de", "it")
_DEFAULT_LOCALE = "pt"

# Canonical tab key → localized URL slug per locale.
# Mirrors frontend/src/middleware.ts::CANONICAL_TO_LOCALE_SLUG.
# The empty-string key represents the ticker root page (no tab slug).
_TAB_SLUGS = {
    "charts":       {"en": "charts", "pt": "graficos", "es": "graficos", "zh": "charts",
                     "fr": "graphiques", "de": "diagramme", "it": "grafici"},
    "fundamentals": {"en": "fundamentals", "pt": "fundamentos", "es": "fundamentos", "zh": "fundamentals",
                     "fr": "fondamentaux", "de": "fundamentaldaten", "it": "fondamentali"},
    "compare":      {"en": "compare", "pt": "comparar", "es": "comparar", "zh": "compare",
                     "fr": "comparer", "de": "vergleich", "it": "confronta"},
}

# Reverse lookup: slug → canonical tab key.
_SLUG_TO_TAB_KEY = {
    slug: tab_key
    for tab_key, per_locale in _TAB_SLUGS.items()
    for slug in per_locale.values()
}

_ALL_TAB_SLUGS = sorted(_SLUG_TO_TAB_KEY.keys())
_LOCALE_ALT = "|".join(_LOCALES)
_SLUG_ALT = "|".join(_ALL_TAB_SLUGS)

# Matches ticker-style URL paths, optionally prefixed with a supported locale:
#   PETR4, PETR4/graficos, en/PETR4, en/PETR4/fundamentals, fr/PETR4/fondamentaux
_TICKER_RE = re.compile(
    rf"^(?:(?P<locale>{_LOCALE_ALT})/)?"
    rf"(?P<ticker>[A-Za-z]{{4}}\d{{1,2}})"
    rf"(?:/(?P<sub>{_SLUG_ALT}))?$"
)

# Frontend SPA routes that should NOT be treated as static file paths
_SPA_ROUTES = {"login", "signup", "forgot-password", "reset-password", "account", "shared"}

_BASE_URL = "https://sponda.capital"


# Localized strings for OG meta / JSON-LD / noscript blocks. Kept in one
# place so every locale gets identical structure and it's trivial to add a
# new locale by extending these dicts.
_TITLE_SUFFIX = {
    "pt": "Indicadores Fundamentalistas",
    "en": "Fundamental Indicators",
    "es": "Indicadores Fundamentales",
    "zh": "基本面指标",
    "fr": "Indicateurs Fondamentaux",
    "de": "Fundamentalkennzahlen",
    "it": "Indicatori Fondamentali",
}

# Breadcrumb labels per tab per locale. The empty-string key is the ticker
# root (no tab suffix).
_TAB_LABELS = {
    "pt": {"": "Indicadores", "charts": "Gráficos", "fundamentals": "Fundamentos", "compare": "Comparar"},
    "en": {"": "Indicators", "charts": "Charts", "fundamentals": "Fundamentals", "compare": "Compare"},
    "es": {"": "Indicadores", "charts": "Gráficos", "fundamentals": "Fundamentos", "compare": "Comparar"},
    "zh": {"": "指标", "charts": "图表", "fundamentals": "基本面", "compare": "对比"},
    "fr": {"": "Indicateurs", "charts": "Graphiques", "fundamentals": "Fondamentaux", "compare": "Comparer"},
    "de": {"": "Kennzahlen", "charts": "Diagramme", "fundamentals": "Fundamentaldaten", "compare": "Vergleich"},
    "it": {"": "Indicatori", "charts": "Grafici", "fundamentals": "Fondamentali", "compare": "Confronta"},
}

_JSON_LD_LANG = {
    "pt": "pt-BR", "en": "en", "es": "es", "zh": "zh-CN",
    "fr": "fr", "de": "de", "it": "it",
}


def _describe_company(locale: str, display_name: str, ticker: str) -> str:
    """Localized description used in og:description, twitter:description, meta description, JSON-LD."""
    if locale == "pt":
        return (
            f"Indicadores fundamentalistas de {display_name} ({ticker}): "
            f"P/L ajustado pela inflação (PE10), P/FCL10, PEG, CAGR e alavancagem. "
            f"Dados atualizados."
        )
    if locale == "en":
        return (
            f"Fundamental indicators for {display_name} ({ticker}): "
            f"inflation-adjusted P/E (PE10), P/FCF10, PEG, CAGR and leverage. "
            f"Updated data."
        )
    if locale == "es":
        return (
            f"Indicadores fundamentales de {display_name} ({ticker}): "
            f"P/E ajustado por inflación (PE10), P/FCF10, PEG, CAGR y apalancamiento. "
            f"Datos actualizados."
        )
    if locale == "zh":
        return f"{display_name} ({ticker}) 基本面指标：通胀调整市盈率 (PE10)、P/FCF10、PEG、CAGR 及杠杆率。数据持续更新。"
    if locale == "fr":
        return (
            f"Indicateurs fondamentaux de {display_name} ({ticker}) : "
            f"P/E ajusté de l'inflation (PE10), P/FCF10, PEG, CAGR et endettement. "
            f"Données actualisées."
        )
    if locale == "de":
        return (
            f"Fundamentalkennzahlen für {display_name} ({ticker}): "
            f"inflationsbereinigtes KGV (PE10), P/FCF10, PEG, CAGR und Verschuldung. "
            f"Aktuelle Daten."
        )
    if locale == "it":
        return (
            f"Indicatori fondamentali di {display_name} ({ticker}): "
            f"P/E corretto per l'inflazione (PE10), P/FCF10, PEG, CAGR e leva finanziaria. "
            f"Dati aggiornati."
        )
    return _describe_company(_DEFAULT_LOCALE, display_name, ticker)


def _noscript_body(locale: str, display_name: str, ticker: str, description: str, sector: str) -> str:
    """Localized <noscript> fallback content for crawlers that don't execute JS."""
    sector_labels = {
        "pt": "Setor", "en": "Sector", "es": "Sector", "zh": "行业",
        "fr": "Secteur", "de": "Sektor", "it": "Settore",
    }
    available_line = {
        "pt": ("Indicadores disponíveis: PE10 (P/L ajustado pela inflação), "
               "P/FCL10, PEG, CAGR do lucro e do fluxo de caixa, Dívida/PL, Passivo/PL e mais."),
        "en": ("Available indicators: PE10 (inflation-adjusted P/E), P/FCF10, "
               "PEG, earnings & free-cash-flow CAGR, Debt/Equity, Liabilities/Equity and more."),
        "es": ("Indicadores disponibles: PE10 (P/E ajustado por inflación), P/FCF10, "
               "PEG, CAGR de beneficios y flujo de caja, Deuda/Patrimonio, Pasivo/Patrimonio y más."),
        "zh": "可用指标：PE10（通胀调整市盈率）、P/FCF10、PEG、利润与自由现金流 CAGR、负债/权益、总负债/权益等。",
        "fr": ("Indicateurs disponibles : PE10 (P/E ajusté de l'inflation), P/FCF10, "
               "PEG, CAGR des bénéfices et du flux de trésorerie, Dette/Capitaux propres, Passif/Capitaux propres et plus."),
        "de": ("Verfügbare Kennzahlen: PE10 (inflationsbereinigtes KGV), P/FCF10, "
               "PEG, CAGR von Gewinn und Free Cashflow, Verschuldung/EK, Fremdkapital/EK und mehr."),
        "it": ("Indicatori disponibili: PE10 (P/E corretto per l'inflazione), P/FCF10, "
               "PEG, CAGR di utili e flusso di cassa, Debito/PN, Passività/PN e altro."),
    }
    back_home = {
        "pt": "Voltar para a página inicial do Sponda",
        "en": "Back to Sponda home",
        "es": "Volver a la página principal de Sponda",
        "zh": "返回 Sponda 首页",
        "fr": "Retour à la page d'accueil de Sponda",
        "de": "Zurück zur Sponda-Startseite",
        "it": "Torna alla home di Sponda",
    }
    heading_suffix = _TITLE_SUFFIX.get(locale, _TITLE_SUFFIX[_DEFAULT_LOCALE])
    sector_line = f"<p>{sector_labels.get(locale, 'Sector')}: {sector}</p>" if sector else ""
    home_href = f"{_BASE_URL}/{locale}" if locale in _LOCALES else _BASE_URL
    return (
        f"<noscript>\n"
        f"      <h1>{display_name} ({ticker}) — {heading_suffix}</h1>\n"
        f"      <p>{description}</p>\n"
        f"      {sector_line}\n"
        f"      <p>{available_line.get(locale, available_line['en'])}</p>\n"
        f'      <p><a href="{home_href}">{back_home.get(locale, back_home["en"])}</a></p>\n'
        f"    </noscript>"
    )


def _inject_og_tags(html: str, ticker: str, path: str = "", locale: str = _DEFAULT_LOCALE) -> str:
    """Inject ticker-specific meta tags, structured data, and noscript content for crawlers.

    `path` is the canonical tab key ("charts", "fundamentals", "compare") or a legacy
    Portuguese slug ("graficos", "fundamentos", "comparar"); both are accepted so existing
    Next.js URL shapes continue to work. `locale` selects the language for every injected
    string (title, description, JSON-LD, noscript); defaults to Portuguese for backward
    compatibility with callers that predate the multi-lingual rollout.
    """
    from quotes.models import Ticker as TickerModel
    from quotes.views import format_display_name

    if locale not in _LOCALES:
        locale = _DEFAULT_LOCALE

    # Normalize `path` to a canonical tab key ("" for ticker root).
    tab_key = _SLUG_TO_TAB_KEY.get(path, "") if path else ""

    ticker_obj = (
        TickerModel.objects.filter(symbol=ticker)
        .values("name", "display_name", "sector")
        .first()
    )
    company_name = (ticker_obj["display_name"] or format_display_name(ticker_obj["name"])) if ticker_obj else ""
    sector = ticker_obj["sector"] if ticker_obj else ""

    display_name = company_name or ticker
    suffix = _TITLE_SUFFIX.get(locale, _TITLE_SUFFIX[_DEFAULT_LOCALE])
    page_title = (
        f"{company_name} ({ticker}) · {suffix} · Sponda"
        if company_name else f"{ticker} · {suffix} · Sponda"
    )
    og_desc = _describe_company(locale, display_name, ticker)

    # Canonical URL embeds the locale prefix (e.g. /en/PETR4/fundamentals) and
    # the localized slug when a tab is selected.
    localized_slug = _TAB_SLUGS[tab_key][locale] if tab_key else ""
    path_tail = f"/{localized_slug}" if localized_slug else ""
    og_url = f"{_BASE_URL}/{locale}/{ticker}{path_tail}"

    replacements = [
        ('property="og:title"', page_title),
        ('property="og:description"', og_desc),
        ('property="og:url"', og_url),
        ('name="twitter:title"', page_title),
        ('name="twitter:description"', og_desc),
        ('name="twitter:card"', "summary_large_image"),
    ]
    for attr, content in replacements:
        html = re.sub(
            rf'<meta\s+{re.escape(attr)}\s+content="[^"]*"\s*/?>',
            f'<meta {attr} content="{content}" />',
            html,
        )

    html = re.sub(r"<title>[^<]*</title>", f"<title>{page_title}</title>", html)

    html = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
        f'<meta name="description" content="{og_desc}" />',
        html,
    )

    html = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
        f'<link rel="canonical" href="{og_url}" />',
        html,
    )

    # Inject ticker-specific JSON-LD structured data (localized).
    dataset_schema = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{suffix} · {display_name} ({ticker})",
        "description": og_desc,
        "url": og_url,
        "keywords": [
            ticker, display_name, "PE10", "PFCF10", "PEG", "CAGR",
        ],
        "creator": {
            "@type": "Organization",
            "name": "Sponda",
            "url": _BASE_URL,
        },
        "inLanguage": _JSON_LD_LANG.get(locale, "en"),
    }
    if sector:
        dataset_schema["about"] = {"@type": "Thing", "name": sector}

    home_item = f"{_BASE_URL}/{locale}"
    ticker_item = f"{_BASE_URL}/{locale}/{ticker}"
    breadcrumb_items = [
        {"@type": "ListItem", "position": 1, "name": "Sponda", "item": home_item},
        {"@type": "ListItem", "position": 2, "name": ticker, "item": ticker_item},
    ]
    if tab_key:
        tab_label = _TAB_LABELS[locale][tab_key]
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

    # Noscript fallback — localized so non-JS crawlers see native-language content.
    noscript_content = _noscript_body(locale, display_name, ticker, og_desc, sector)
    html = re.sub(
        r"<noscript>.*?</noscript>",
        noscript_content,
        html,
        flags=re.DOTALL,
    )

    return html


def _serve_frontend(request, filepath=""):
    """Serve the built frontend SPA. Falls back to index.html for client-side routing.

    For ticker pages (e.g. /PETR4, /en/PETR4, /fr/PETR4/fondamentaux), injects meta tags
    and structured data server-side so social media crawlers see locale-correct content.
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

    ticker_match = _TICKER_RE.match(filepath) if filepath else None
    if ticker_match:
        html = index.read_text()
        ticker = ticker_match.group("ticker").upper()
        locale = ticker_match.group("locale") or _DEFAULT_LOCALE
        sub = ticker_match.group("sub") or ""
        html = _inject_og_tags(html, ticker, sub, locale=locale)
        return HttpResponse(html, content_type="text/html")

    return FileResponse(open(index, "rb"), content_type="text/html")


def _serve_sitemap(request):
    """Serve sitemap.xml at the root URL by proxying to the API endpoint."""
    from quotes.views import SitemapView

    return SitemapView.as_view()(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", _serve_sitemap, name="sitemap-root"),
    path("api/", include("quotes.urls")),
    path("api/auth/", include("accounts.urls")),
    re_path(r"^(?P<filepath>assets/.*)$", _serve_frontend),
    re_path(r"^(?!api/|admin/)(?P<filepath>.*)$", _serve_frontend),
]
