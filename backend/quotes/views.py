import hashlib
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from .providers import ProviderError, fetch_dividends, fetch_historical_prices, fetch_quote, sync_balance_sheets, sync_cash_flows, sync_earnings
from .fundamentals import aggregate_proventos_by_year, compute_fundamentals
from .leverage import calculate_leverage
from .models import BalanceSheet, CompanyAnalysis, IPCAIndex, LookupLog, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from .multiples_history import compute_multiples_history
from .pe10 import calculate_pe10
from .peg import calculate_peg
from .pfcf10 import calculate_pfcf10
from .pfcf_peg import calculate_pfcf_peg

PE10_CACHE_TTL = 5 * 60  # 5 minutes
FUNDAMENTALS_CACHE_TTL = 10 * 60  # 10 minutes


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


TICKER_LIST_CACHE_KEY = "ticker_list_v1"
TICKER_LIST_CACHE_TIMEOUT = 3600  # 1 hour

class TickerListView(APIView):
    def get(self, request):
        result = cache.get(TICKER_LIST_CACHE_KEY)
        if result is None:
            tickers = Ticker.objects.filter(type="stock").exclude(symbol__regex=r"^[A-Z]+\d+F$").values("symbol", "name", "display_name", "sector", "type", "logo")
            result = []
            for ticker in tickers:
                ticker["name"] = ticker.pop("display_name") or ticker["name"]
                result.append(ticker)
            cache.set(TICKER_LIST_CACHE_KEY, result, TICKER_LIST_CACHE_TIMEOUT)
        response = Response(result)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class TickerDetailView(APIView):
    def get(self, request, symbol):
        cache_key = f"ticker_detail_{symbol.upper()}"
        result = cache.get(cache_key)
        if result is None:
            try:
                ticker = Ticker.objects.filter(
                    symbol__iexact=symbol, type="stock"
                ).values("symbol", "name", "display_name", "sector", "type", "logo").first()
            except Ticker.DoesNotExist:
                ticker = None
            if ticker is None:
                return Response({"detail": "Not found"}, status=404)
            ticker["name"] = ticker.pop("display_name") or ticker["name"]
            result = ticker
            cache.set(cache_key, result, TICKER_LIST_CACHE_TIMEOUT)
        response = Response(result)
        response["Cache-Control"] = "public, max-age=3600"
        return response


FINANCE_SUBSECTOR_RULES = [
    (re.compile(r"\bBCO\b|BANCO\b|BANESTES|ITAU|BRADESC|BANESE", re.IGNORECASE), "Bancos"),
    (re.compile(r"SEGUR|SEGURAD|RESSEGURO", re.IGNORECASE), "Seguros"),
    (re.compile(r"CONSTRU|INCORPOR|EMPREEND.*IMOB|REALTY|ENGENHARIA|TENDA|CURY|CYRELA|DIRECIONAL|EVEN|GAFISA|LAVVI|MITRE|MOURA|PLANO|TECNISA|PDG|ALPHAVILLE", re.IGNORECASE), "Construção e Incorporação"),
    (re.compile(r"SHOPPING|IGUATEMI|MULTIPLAN|ALLOS", re.IGNORECASE), "Shoppings"),
    (re.compile(r"LOCAÇÃO|LOCACAO|RENT A CAR|MOVIDA|VAMOS|ARMAC|MILLS", re.IGNORECASE), "Locação"),
    (re.compile(r"AGRO|AGRICOLA|TERRA SANTA", re.IGNORECASE), "Agronegócio"),
    (re.compile(r"BOLSA|BALCÃO|B3 S\.A", re.IGNORECASE), "Infraestrutura de Mercado"),
    (re.compile(r"HOLDING|PARTICIPAC", re.IGNORECASE), "Holdings"),
]


def get_subsector(name, sector):
    if sector == "Finance":
        for pattern, subsector in FINANCE_SUBSECTOR_RULES:
            if pattern.search(name):
                return subsector
    return sector


def ticker_base(symbol):
    return re.sub(r"\d+$", "", symbol)


def deduplicate_by_company(tickers):
    suffix_priority = {"4": 0, "3": 1, "11": 2}
    best = {}
    for ticker in tickers:
        base = ticker_base(ticker["symbol"])
        suffix = ticker["symbol"][len(base):]
        priority = suffix_priority.get(suffix, 9)
        existing = best.get(base)
        if existing is None or priority < existing["priority"]:
            best[base] = {**ticker, "priority": priority}
    return [{k: v for k, v in entry.items() if k != "priority"} for entry in best.values()]


class TickerPeersView(APIView):
    MAX_PEERS = 10
    MIN_PEERS = 3
    CACHE_TIMEOUT = 3600

    def get(self, request, symbol):
        symbol_upper = symbol.upper()
        cache_key = f"ticker_peers_{symbol_upper}"
        cached = cache.get(cache_key)
        if cached is not None:
            response = Response(cached)
            response["Cache-Control"] = "public, max-age=3600"
            return response

        current = Ticker.objects.filter(
            symbol__iexact=symbol, type="stock"
        ).values("symbol", "name", "display_name", "sector").first()

        if current is None:
            return Response({"detail": "Not found"}, status=404)

        current_name = current["display_name"] or current["name"]
        current_sector = current["sector"]
        current_base = ticker_base(current["symbol"])

        if not current_sector:
            result = []
        else:
            all_sector_tickers = list(
                Ticker.objects.filter(type="stock", sector=current_sector)
                .exclude(symbol__regex=r"^[A-Z]+\d+F$")
                .values("symbol", "name", "display_name", "sector")
            )
            for ticker in all_sector_tickers:
                ticker["name"] = ticker.pop("display_name") or ticker["name"]

            current_subsector = get_subsector(current_name, current_sector)

            subsector_matches = [
                t for t in all_sector_tickers
                if ticker_base(t["symbol"]) != current_base
                and get_subsector(t["name"], t["sector"]) == current_subsector
            ]
            subsector_peers = deduplicate_by_company(subsector_matches)[:self.MAX_PEERS]

            if len(subsector_peers) >= self.MIN_PEERS:
                result = [{"symbol": p["symbol"], "name": p["name"]} for p in subsector_peers]
            else:
                sector_matches = [
                    t for t in all_sector_tickers
                    if ticker_base(t["symbol"]) != current_base
                ]
                sector_peers = deduplicate_by_company(sector_matches)[:self.MAX_PEERS]
                result = [{"symbol": p["symbol"], "name": p["name"]} for p in sector_peers]

        cache.set(cache_key, result, self.CACHE_TIMEOUT)
        response = Response(result)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class TickerSearchView(APIView):
    """Fast server-side ticker search. Returns up to 8 matches.

    Always blends symbol prefix matches with name matches so that
    popular companies surface even when many obscure tickers share
    the same prefix (e.g. typing "mic" shows Microsoft alongside
    MIC, MICC, etc.).
    """

    SEARCH_LIMIT = 8
    MAX_SYMBOL_MATCHES = 5
    MIN_NAME_SLOTS = 3

    SEARCH_CACHE_TIMEOUT = 120  # 2 minutes

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 1:
            return Response([])

        # Check cache first
        cache_key = f"search:{hashlib.md5(query.lower().encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached is not None:
            response = Response(cached)
            response["Cache-Control"] = "public, max-age=60"
            return response

        query_upper = query.upper()
        market_cap_ordering = F("market_cap").desc(nulls_last=True)
        exclude_fractional = r"^[A-Z]+\d+F$"

        fields = ("symbol", "name", "display_name", "sector", "type", "logo", "market_cap")

        # Symbol prefix matches (capped to leave room for name matches)
        symbol_matches = list(
            Ticker.objects.filter(type="stock", symbol__istartswith=query_upper)
            .exclude(symbol__regex=exclude_fractional)
            .order_by(market_cap_ordering)
            .values(*fields)
            [:self.MAX_SYMBOL_MATCHES]
        )

        # Name matches (always fetched to blend in popular companies)
        found_symbols = {r["symbol"] for r in symbol_matches}
        name_slots = max(self.MIN_NAME_SLOTS, self.SEARCH_LIMIT - len(symbol_matches))
        name_matches = list(
            Ticker.objects.filter(type="stock", display_name__icontains=query)
            .exclude(symbol__in=found_symbols)
            .exclude(symbol__regex=exclude_fractional)
            .order_by(market_cap_ordering)
            .values(*fields)
            [:name_slots]
        )

        # Merge and sort: all results together, ranked by market cap
        results = symbol_matches + name_matches
        results.sort(key=lambda r: (r["market_cap"] is None, -(r["market_cap"] or 0)))
        results = results[:self.SEARCH_LIMIT]

        for ticker in results:
            ticker["name"] = ticker.pop("display_name") or ticker["name"]
            del ticker["market_cap"]

        cache.set(cache_key, results, self.SEARCH_CACHE_TIMEOUT)

        response = Response(results)
        response["Cache-Control"] = "public, max-age=60"
        return response


class HealthView(APIView):
    TICKER_STALENESS_THRESHOLD = timedelta(days=2)
    IPCA_STALENESS_THRESHOLD = timedelta(days=45)

    def get(self, request):
        latest_ticker = Ticker.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
        tickers_stale = latest_ticker is None or (timezone.now() - latest_ticker) > self.TICKER_STALENESS_THRESHOLD

        latest_ipca = IPCAIndex.objects.order_by("-date").values_list("date", flat=True).first()
        ipca_stale = latest_ipca is None or (date.today() - latest_ipca) > self.IPCA_STALENESS_THRESHOLD

        is_healthy = not tickers_stale and not ipca_stale

        return Response({
            "status": "ok" if is_healthy else "degraded",
            "tickers": {
                "stale": tickers_stale,
                "last_updated": latest_ticker,
            },
            "ipca": {
                "stale": ipca_stale,
                "latest_date": latest_ipca,
            },
        })


def _ensure_fresh_data(ticker: str) -> None:
    """Sync earnings, cash flows, and balance sheets if older than 24h."""
    cutoff = timezone.now() - timedelta(hours=24)

    has_fresh_earnings = QuarterlyEarnings.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_earnings:
        try:
            sync_earnings(ticker)
        except ProviderError:
            pass

    has_fresh_cf = QuarterlyCashFlow.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_cf:
        try:
            sync_cash_flows(ticker)
        except ProviderError:
            pass

    has_fresh_bs = BalanceSheet.objects.filter(
        ticker=ticker, fetched_at__gte=cutoff
    ).exists()
    if not has_fresh_bs:
        try:
            sync_balance_sheets(ticker)
        except ProviderError:
            pass


class PE10View(APIView):
    def get(self, request, ticker):
        ticker = ticker.upper()

        cache_key = f"pe10:{ticker}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self._log_lookup(request, ticker)
            return Response(cached_result)

        # Ensure we have fresh data (< 24h old)
        _ensure_fresh_data(ticker)

        # Fetch current price
        try:
            quote = fetch_quote(ticker)
        except ProviderError as e:
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

        result = {
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
        }
        cache.set(cache_key, result, PE10_CACHE_TTL)
        return Response(result)

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
        except ProviderError as e:
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
        except ProviderError:
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

        cache_key = f"fundamentals:{ticker}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            response = Response(cached_result)
            response["Cache-Control"] = "public, max-age=3600"
            return response

        _ensure_fresh_data(ticker)

        try:
            quote = fetch_quote(ticker)
        except ProviderError as e:
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
        except ProviderError:
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
            except ProviderError:
                pass

        fundamentals = compute_fundamentals(
            ticker,
            market_cap=market_cap_float,
            current_price=current_price_float,
            historical_prices=historical_prices,
            proventos_by_year=proventos_by_year,
        )

        cache.set(cache_key, fundamentals, FUNDAMENTALS_CACHE_TTL)
        response = Response(fundamentals)
        response["Cache-Control"] = "public, max-age=3600"
        return response



class CompanyAnalysisView(APIView):
    """Return the latest analysis and version history for a ticker."""

    def get(self, request, ticker):
        ticker = ticker.upper()

        analyses = list(
            CompanyAnalysis.objects.filter(ticker=ticker)
            .order_by("-generated_at")
            .values("id", "content", "data_quarter", "generated_at")
        )

        if not analyses:
            return Response(
                {"error": "Nenhuma análise disponível para este ticker."},
                status=status.HTTP_404_NOT_FOUND,
            )

        latest = analyses[0]
        versions = [
            {
                "id": analysis["id"],
                "dataQuarter": analysis["data_quarter"],
                "generatedAt": analysis["generated_at"].isoformat(),
            }
            for analysis in analyses
        ]

        response = Response({
            "ticker": ticker,
            "content": latest["content"],
            "dataQuarter": latest["data_quarter"],
            "generatedAt": latest["generated_at"].isoformat(),
            "versions": versions,
        })
        response["Cache-Control"] = "public, max-age=3600"
        return response


LOGO_CACHE_MAX_AGE = 30 * 24 * 3600  # 30 days


def detect_image_content_type(data: bytes) -> str:
    """Detect image content type from file magic bytes."""
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if b"<svg" in data[:256]:
        return "image/svg+xml"
    return "image/png"


class LogoProxyView(APIView):
    """Proxy and cache company logos on our server."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, symbol):
        symbol = symbol.upper()
        if not re.match(r"^[A-Z0-9.]+$", symbol):
            return HttpResponse(status=404)

        cache_dir = Path(settings.LOGO_CACHE_DIR)
        cached_path = cache_dir / f"{symbol}.png"

        if cached_path.exists():
            image_data = cached_path.read_bytes()
            content_type = detect_image_content_type(image_data)
            response = HttpResponse(image_data, content_type=content_type)
            response["Cache-Control"] = f"public, max-age={LOGO_CACHE_MAX_AGE}"
            return response

        try:
            ticker = Ticker.objects.get(symbol=symbol)
        except Ticker.DoesNotExist:
            return HttpResponse(status=404)

        if not ticker.logo:
            return HttpResponse(status=404)

        try:
            logo_request = Request(ticker.logo, headers={"User-Agent": "Sponda/1.0"})
            with urlopen(logo_request, timeout=10) as logo_response:
                image_data = logo_response.read()
        except Exception:
            logger.warning("Failed to download logo for %s from %s", symbol, ticker.logo)
            return HttpResponse(status=404)

        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path.write_bytes(image_data)

        content_type = detect_image_content_type(image_data)
        response = HttpResponse(image_data, content_type=content_type)
        response["Cache-Control"] = f"public, max-age={LOGO_CACHE_MAX_AGE}"
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
