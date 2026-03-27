import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .brapi import BRAPIError, fetch_dividends, fetch_historical_prices, fetch_quote, sync_balance_sheets, sync_cash_flows, sync_earnings
from .fundamentals import aggregate_proventos_by_year, compute_fundamentals
from .leverage import calculate_leverage
from .models import BalanceSheet, LookupLog, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from .multiples_history import compute_multiples_history
from .og_image import generate_homepage_og_image, generate_og_image
from .pe10 import calculate_pe10
from .peg import calculate_peg
from .pfcf10 import calculate_pfcf10
from .pfcf_peg import calculate_pfcf_peg


def _clean_company_name(name: str) -> str:
    """Strip legal suffixes and ticker-like noise from a company name.

    'Petroleo Brasileiro SA Pfd' → 'Petroleo Brasileiro'
    'Eucatex S.A. Industria E Comercio' → 'Eucatex'
    'PETR3' (ticker as name) → 'PETR3' (unchanged — no suffix to strip)
    """
    # Remove common Brazilian legal suffixes and share class markers
    suffixes = r"(?:S[\./]?A\.?|Ltda\.?|Cia\.?|Pfd|ON|PN|NM|N[12]|EDJ)"
    # Remove from first suffix onward (greedy: keeps the meaningful part)
    cleaned = re.split(rf"\s+{suffixes}(?:\s|$)", name, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip() or name


# Words that should stay lowercase in title case (Portuguese prepositions/articles)
_LOWERCASE_WORDS = {"de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas"}

# Common abbreviation expansions for formal BRAPI names
_ABBREVIATIONS = {
    "BCO": "Banco",
    "CIA": "Cia",
}

# Words to strip (legal/corporate noise that adds no value)
_STRIP_WORDS = {"PARTICIPAÇÕES", "PARTICIPACOES", "HOLDING", "EMPREENDIMENTOS",
                "INVESTIMENTOS", "INVESTIMENTO", "SERVICOS", "SERVIÇOS",
                "FINANCEIROS"}

# Accent corrections for well-known names
_ACCENT_FIXES = {
    "itau": "Itaú",
    "itausa": "Itaúsa",
    "sao": "São",
    "siderurgica": "Siderúrgica",
    "acucar": "Açúcar",
    "comercio": "Comércio",
    "ceramica": "Cerâmica",
    "eletrica": "Elétrica",
    "energetica": "Energética",
    "metalurgica": "Metalúrgica",
}


def _title_case_word(word: str, index: int) -> str:
    """Title-case a single word, respecting Portuguese conventions."""
    lower = word.lower()
    if lower in _ACCENT_FIXES:
        return _ACCENT_FIXES[lower]
    if index > 0 and lower in _LOWERCASE_WORDS:
        return lower
    # Preserve known acronyms (2-3 letter all-caps that aren't common words)
    _COMMON_SHORT_WORDS = {"RIO", "SUL", "SAO", "PET", "CEA", "BOA", "VIA", "CAR", "MAR"}
    if word.isupper() and 2 <= len(word) <= 3 and word not in _COMMON_SHORT_WORDS:
        return word
    return word.capitalize()


def format_display_name(formal_name: str) -> str:
    """Convert a formal BRAPI ticker name into a human-friendly display name.

    'PETROLEO BRASILEIRO S.A. PETROBRAS' → 'Petrobras'
    'BCO BRASIL S.A.' → 'Banco do Brasil'
    'CIA PARANAENSE DE ENERGIA - COPEL' → 'Copel'
    'VALE S.A.' → 'Vale'
    """
    if not formal_name:
        return ""

    # If it looks like a bare ticker symbol (e.g. "MBRF3"), return as-is
    if re.match(r"^[A-Z]{3,5}\d{1,2}$", formal_name):
        return formal_name

    # Check for trade name around dash (e.g., "CIA PARANAENSE DE ENERGIA - COPEL")
    if " - " in formal_name:
        before_dash, after_dash = formal_name.rsplit(" - ", 1)
        # If the part before the dash is short after stripping S.A., prefer it (e.g., "B3 S.A.")
        before_core = re.sub(r"\s+S[\./]?A\.?.*$", "", before_dash, flags=re.IGNORECASE).strip()
        if before_core and len(before_core.split()) <= 2:
            return " ".join(_title_case_word(w, i) for i, w in enumerate(before_core.split()))
        # Otherwise use the after-dash part if it's a short trade name
        after_cleaned = re.sub(r"\s+S[\./]?A\.?.*$", "", after_dash, flags=re.IGNORECASE).strip()
        if after_cleaned and len(after_cleaned.split()) <= 3:
            return " ".join(_title_case_word(w, i) for i, w in enumerate(after_cleaned.split()))

    # Check for trade name after legal suffix
    # e.g., "PETROLEO BRASILEIRO S.A. PETROBRAS" → extract "PETROBRAS"
    sa_match = re.search(r"\bS[\./]?A\.?\s+(.+)$", formal_name, re.IGNORECASE)
    if sa_match:
        trade_name = sa_match.group(1).strip()
        # Only use it if it's a single trade name word (not a descriptive phrase)
        trade_words = trade_name.split()
        if len(trade_words) == 1 and not any(w.upper() in _STRIP_WORDS for w in trade_words):
            return " ".join(_title_case_word(w, i) for i, w in enumerate(trade_words))

    # Strip legal suffixes: S.A., S/A, etc. and everything after
    cleaned = re.split(r"\s+S[\./]?A\.?(?:\s|$)", formal_name, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = cleaned.strip().rstrip(".")

    # Expand abbreviations
    words = cleaned.split()
    expanded = []
    for word in words:
        upper = word.upper()
        if upper in _ABBREVIATIONS:
            expanded.append(_ABBREVIATIONS[upper])
        elif upper in _STRIP_WORDS:
            continue
        else:
            expanded.append(word)
    words = expanded

    # Insert "do" after "Banco" only for geographic/institutional names
    _BANCO_DO_TARGETS = {"BRASIL", "AMAZONIA", "NORDESTE", "ESTADO"}
    if len(words) >= 2 and words[0] == "Banco" and words[1].upper() in _BANCO_DO_TARGETS:
        words.insert(1, "do")

    # Title case
    result = " ".join(_title_case_word(w, i) for i, w in enumerate(words))

    # Strip trailing prepositions/articles left over from word removal
    result = re.sub(r"\s+(?:de|do|da|dos|das|e|em)\s*$", "", result, flags=re.IGNORECASE)

    return result.strip()


class TickerListView(APIView):
    def get(self, request):
        tickers = Ticker.objects.filter(type="stock").exclude(symbol__regex=r"^[A-Z]+\d+F$").values("symbol", "name", "display_name", "sector", "type", "logo")
        result = []
        for ticker in tickers:
            ticker["name"] = ticker.pop("display_name") or ticker["name"]
            result.append(ticker)
        response = Response(result)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


def _ensure_fresh_data(ticker: str) -> None:
    """Sync earnings, cash flows, and balance sheets if older than 24h."""
    cutoff = timezone.now() - timedelta(hours=24)

    has_fresh_earnings = QuarterlyEarnings.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_earnings:
        try:
            sync_earnings(ticker)
        except BRAPIError:
            pass

    has_fresh_cf = QuarterlyCashFlow.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_cf:
        try:
            sync_cash_flows(ticker)
        except BRAPIError:
            pass

    has_fresh_bs = BalanceSheet.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_bs:
        try:
            sync_balance_sheets(ticker)
        except BRAPIError:
            pass


class PE10View(APIView):
    def get(self, request, ticker):
        ticker = ticker.upper()

        # Ensure we have fresh data (< 24h old)
        _ensure_fresh_data(ticker)

        # Fetch current price
        try:
            quote = fetch_quote(ticker)
        except BRAPIError as e:
            msg = str(e)
            if "No results" in msg:
                return Response(
                    {"error": f'Ticker "{ticker}" não encontrado. Verifique o código e tente novamente.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"error": "Não foi possível obter os dados no momento. Tente novamente mais tarde."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        current_price = Decimal(str(quote.get("regularMarketPrice", 0)))
        name = _clean_company_name(
            quote.get("longName") or quote.get("shortName") or ticker
        )
        market_cap = quote.get("marketCap")

        if not market_cap or not current_price:
            return Response(
                {"error": "Dados de mercado indisponíveis para este ticker."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        market_cap_decimal = Decimal(str(market_cap))

        # Get logo from Ticker table
        logo = ""
        try:
            logo = Ticker.objects.values_list("logo", flat=True).get(symbol=ticker)
        except Ticker.DoesNotExist:
            pass

        # Calculate metrics — fetch all available years; frontend slices as needed
        pe10_result = calculate_pe10(ticker, market_cap_decimal, max_years=50)
        pfcf10_result = calculate_pfcf10(ticker, market_cap_decimal, max_years=50)
        max_years_available = max(pe10_result["years_of_data"], pfcf10_result["years_of_data"])
        leverage_result = calculate_leverage(ticker)
        peg_result = calculate_peg(ticker, pe10_result["pe10"], max_years=50)
        pfcf_peg_result = calculate_pfcf_peg(ticker, pfcf10_result["pfcf10"], max_years=50)

        # Debt / average earnings and debt / average FCF
        total_debt = leverage_result["totalDebt"]
        avg_earnings = pe10_result["avg_adjusted_net_income"]
        avg_fcf = pfcf10_result["avg_adjusted_fcf"]

        debt_to_avg_earnings = None
        if total_debt is not None and avg_earnings and avg_earnings > 0:
            debt_to_avg_earnings = round(total_debt / avg_earnings, 2)

        debt_to_avg_fcf = None
        if total_debt is not None and avg_fcf and avg_fcf > 0:
            debt_to_avg_fcf = round(total_debt / avg_fcf, 2)

        # Log the lookup
        self._log_lookup(request, ticker)

        return Response({
            "ticker": ticker,
            "name": name,
            "logo": logo,
            "currentPrice": float(current_price),
            "marketCap": market_cap,
            "maxYearsAvailable": max_years_available,
            # PE10
            "pe10": pe10_result["pe10"],
            "avgAdjustedNetIncome": pe10_result["avg_adjusted_net_income"],
            "pe10YearsOfData": pe10_result["years_of_data"],
            "pe10Label": pe10_result["label"],
            "pe10Error": pe10_result["error"],
            "pe10AnnualData": pe10_result["annual_data_flag"],
            "pe10CalculationDetails": pe10_result["calculation_details"],
            # PFCF10
            "pfcf10": pfcf10_result["pfcf10"],
            "avgAdjustedFCF": pfcf10_result["avg_adjusted_fcf"],
            "pfcf10YearsOfData": pfcf10_result["years_of_data"],
            "pfcf10Label": pfcf10_result["label"],
            "pfcf10Error": pfcf10_result["error"],
            "pfcf10AnnualData": pfcf10_result["annual_data_flag"],
            "pfcf10CalculationDetails": pfcf10_result["calculation_details"],
            # Leverage
            "debtToEquity": leverage_result["debtToEquity"],
            "debtExLeaseToEquity": leverage_result["debtExLeaseToEquity"],
            "liabilitiesToEquity": leverage_result["liabilitiesToEquity"],
            "currentRatio": leverage_result["currentRatio"],
            "leverageError": leverage_result["leverageError"],
            "leverageDate": leverage_result["leverageDate"],
            "totalDebt": leverage_result["totalDebt"],
            "totalLease": leverage_result["totalLease"],
            "totalLiabilities": leverage_result["totalLiabilities"],
            "stockholdersEquity": leverage_result["stockholdersEquity"],
            # Debt coverage
            "debtToAvgEarnings": debt_to_avg_earnings,
            "debtToAvgFCF": debt_to_avg_fcf,
            # PEG
            "peg": peg_result["peg"],
            "earningsCAGR": peg_result["earningsCAGR"],
            "pegError": peg_result["pegError"],
            "earningsCAGRMethod": peg_result["earningsCAGRMethod"],
            "earningsCAGRExcludedYears": peg_result["earningsCAGRExcludedYears"],
            # PFCLG
            "pfcfPeg": pfcf_peg_result["pfcfPeg"],
            "fcfCAGR": pfcf_peg_result["fcfCAGR"],
            "pfcfPegError": pfcf_peg_result["pfcfPegError"],
            "fcfCAGRMethod": pfcf_peg_result["fcfCAGRMethod"],
            "fcfCAGRExcludedYears": pfcf_peg_result["fcfCAGRExcludedYears"],
        })

    DAILY_DISTINCT_TICKER_LIMIT = 200

    def _check_rate_limit(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if request.user.is_authenticated:
            distinct_tickers = LookupLog.objects.filter(
                user=request.user, timestamp__gte=today_start
            ).values("ticker").distinct().count()
        else:
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            distinct_tickers = LookupLog.objects.filter(
                session_key=session_key, timestamp__gte=today_start
            ).values("ticker").distinct().count()

        if distinct_tickers >= self.DAILY_DISTINCT_TICKER_LIMIT:
            return Response(
                {
                    "error": "Limite diário de consultas atingido. Tente novamente amanhã.",
                    "limit": self.DAILY_DISTINCT_TICKER_LIMIT,
                    "used": distinct_tickers,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return None

    def _log_lookup(self, request, ticker):
        if request.user.is_authenticated:
            LookupLog.objects.create(user=request.user, ticker=ticker)
        else:
            if not request.session.session_key:
                request.session.create()
            LookupLog.objects.create(
                session_key=request.session.session_key, ticker=ticker
            )


class MultiplesHistoryView(APIView):
    """Return historical prices and year-end P/L, P/FCL multiples."""

    def get(self, request, ticker):
        ticker = ticker.upper()

        _ensure_fresh_data(ticker)

        try:
            quote = fetch_quote(ticker)
        except BRAPIError as e:
            msg = str(e)
            if "No results" in msg:
                return Response(
                    {"error": f'Ticker "{ticker}" não encontrado.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"error": "Não foi possível obter os dados no momento. Tente novamente mais tarde."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        current_price = float(quote.get("regularMarketPrice", 0))
        market_cap = quote.get("marketCap")

        if not market_cap or not current_price:
            return Response(
                {"error": "Dados de mercado indisponíveis para este ticker."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            historical = fetch_historical_prices(ticker)
        except BRAPIError:
            return Response(
                {"error": "Não foi possível obter os dados históricos. Tente novamente mais tarde."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        result = compute_multiples_history(
            ticker=ticker,
            historical_prices=historical,
            market_cap=float(market_cap),
            current_price=current_price,
        )

        response = Response(result)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class FundamentalsView(APIView):
    """Return per-year fundamental data for the Fundamentos tab."""

    def get(self, request, ticker):
        ticker = ticker.upper()

        _ensure_fresh_data(ticker)

        try:
            quote = fetch_quote(ticker)
        except BRAPIError as e:
            msg = str(e)
            if "No results" in msg:
                return Response(
                    {"error": f'Ticker "{ticker}" não encontrado.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"error": "Não foi possível obter os dados no momento. Tente novamente mais tarde."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        market_cap = quote.get("marketCap")
        current_price = quote.get("regularMarketPrice")

        try:
            historical_prices = fetch_historical_prices(ticker)
        except BRAPIError:
            historical_prices = []

        # Fetch dividend data and compute total proventos per year
        proventos_by_year = None
        current_price_float = float(current_price) if current_price else None
        market_cap_float = float(market_cap) if market_cap else None
        if market_cap_float and current_price_float and current_price_float > 0:
            try:
                dividends_data = fetch_dividends(ticker)
                current_shares = market_cap_float / current_price_float
                proventos_by_year = aggregate_proventos_by_year(
                    cash_dividends=dividends_data["cashDividends"],
                    stock_dividends=dividends_data["stockDividends"],
                    current_shares=current_shares,
                )
            except BRAPIError:
                pass

        fundamentals = compute_fundamentals(
            ticker,
            market_cap=market_cap_float,
            current_price=current_price_float,
            historical_prices=historical_prices,
            proventos_by_year=proventos_by_year,
        )

        response = Response(fundamentals)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class OGImageView(APIView):
    """Generate Open Graph images for social sharing."""

    def get(self, request, ticker=None):
        if ticker is None:
            png = generate_homepage_og_image()
            response = HttpResponse(png, content_type="image/png")
            response["Cache-Control"] = "public, max-age=86400"
            return response

        ticker = ticker.upper()

        name = ticker
        logo_url = None
        ticker_obj = Ticker.objects.filter(symbol=ticker).values("name", "display_name", "logo").first()
        if ticker_obj:
            name = ticker_obj["display_name"] or format_display_name(ticker_obj["name"]) or ticker
            logo_url = ticker_obj.get("logo") or None

        png = generate_og_image(ticker=ticker, name=name, logo_url=logo_url)

        response = HttpResponse(png, content_type="image/png")
        response["Cache-Control"] = "public, max-age=3600"
        return response


class SitemapView(APIView):
    """Generate a dynamic XML sitemap with all stock ticker pages."""

    def get(self, request):
        base_url = "https://sponda.capital"
        tickers = (
            Ticker.objects.filter(type="stock")
            .exclude(symbol__regex=r"^[A-Z]+\d+F$")
            .values_list("symbol", "updated_at")
            .order_by("symbol")
        )

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            "  <url>",
            f"    <loc>{base_url}/</loc>",
            "    <changefreq>daily</changefreq>",
            "    <priority>1.0</priority>",
            "  </url>",
        ]

        sub_pages = [
            ("", "0.8", "weekly"),
            ("/fundamentos", "0.6", "weekly"),
            ("/graficos", "0.5", "weekly"),
            ("/comparar", "0.4", "monthly"),
        ]

        for symbol, updated_at in tickers:
            lastmod = updated_at.strftime("%Y-%m-%d") if updated_at else ""
            for suffix, priority, changefreq in sub_pages:
                lines.append("  <url>")
                lines.append(f"    <loc>{base_url}/{symbol}{suffix}</loc>")
                if lastmod:
                    lines.append(f"    <lastmod>{lastmod}</lastmod>")
                lines.append(f"    <changefreq>{changefreq}</changefreq>")
                lines.append(f"    <priority>{priority}</priority>")
                lines.append("  </url>")

        lines.append("</urlset>")

        xml = "\n".join(lines)
        response = HttpResponse(xml, content_type="application/xml")
        response["Cache-Control"] = "public, max-age=86400"
        return response
