import hashlib
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from .fmp import FMPError, fetch_profile
from .logo_overrides import LOGO_OVERRIDE_URLS, is_placeholder_logo_url
from .providers import ProviderError, is_brazilian_ticker, fetch_dividends, fetch_historical_prices, fetch_quote, sync_balance_sheets, sync_cash_flows, sync_earnings
from .fundamentals import aggregate_proventos_by_year, compute_fundamentals, compute_quarterly_balance_ratios
from .leverage import calculate_leverage
from .models import BalanceSheet, CompanyAnalysis, IndicatorSnapshot, IPCAIndex, LookupLog, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from .multiples_history import compute_multiples_history
from .pe10 import calculate_pe10
from .peg import calculate_peg
from .pfcf10 import calculate_pfcf10
from .pfcf_peg import calculate_pfcf_peg

PE10_CACHE_TTL = 24 * 60 * 60  # 24 hours
FUNDAMENTALS_CACHE_TTL = 24 * 60 * 60  # 24 hours
MULTIPLES_HISTORY_CACHE_TTL = 24 * 60 * 60  # 24 hours


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


# Per-sector subsector rules. Each sector's entry is an ordered list of
# (regex, subsector-label). First match wins. Companies that don't match any
# rule fall back to the sector's default subsector defined in SUBSECTOR_DEFAULT.
#
# Subsectors let peer ranking prefer companies in the *same* business line
# before filling with other companies in the same broader sector.
SUBSECTOR_RULES = {
    "Finance": [
        (re.compile(r"\bBCO\b|BANCO\b|BANESTES|ITAU|BRADESC|BANESE", re.IGNORECASE), "Bancos"),
        (re.compile(r"SEGUR|SEGURAD|RESSEGURO", re.IGNORECASE), "Seguros"),
        (re.compile(r"CONSTRU|INCORPOR|EMPREEND.*IMOB|REALTY|ENGENHARIA|TENDA|CURY|CYRELA|DIRECIONAL|EVEN|GAFISA|LAVVI|MITRE|MOURA|PLANO|TECNISA|PDG|ALPHAVILLE", re.IGNORECASE), "Construção e Incorporação"),
        (re.compile(r"SHOPPING|IGUATEMI|MULTIPLAN|ALLOS", re.IGNORECASE), "Shoppings"),
        (re.compile(r"LOCAÇÃO|LOCACAO|RENT A CAR|MOVIDA|VAMOS|ARMAC|MILLS", re.IGNORECASE), "Locação"),
        (re.compile(r"AGRO|AGRICOLA|TERRA SANTA", re.IGNORECASE), "Agronegócio"),
        (re.compile(r"BOLSA|BALCÃO|B3 S\.A", re.IGNORECASE), "Infraestrutura de Mercado"),
        (re.compile(r"HOLDING|PARTICIPAC", re.IGNORECASE), "Holdings"),
    ],
    "Non-Energy Minerals": [
        (re.compile(r"PAPEL|CELULOSE|KLABIN|SUZANO|IRANI", re.IGNORECASE), "Papel e Celulose"),
        (re.compile(r"ETERNIT|EUCATEX|CIMENT|CERAMIC|MADEIRA", re.IGNORECASE), "Materiais de Construção"),
        (re.compile(r"ALUMÍN|ALUMIN|COBRE|NIQUEL|PARANAPANEMA|TEKNO|METAIS NÃO|METAIS NAO", re.IGNORECASE), "Metais Não-Ferrosos"),
    ],
    "Process Industries": [
        (re.compile(r"PAPEL|CELULOSE|EMBALAG|IRANI|KLABIN|SUZANO", re.IGNORECASE), "Papel e Embalagens"),
        (re.compile(r"AGRÍC|AGRIC|ALIMENT|SEMENTES|SAFRA|MARTINHO|CAMIL|AÇÚCAR|ACUCAR|JALLES|SOJA|BOA SAFRA|SLC", re.IGNORECASE), "Agro e Alimentos"),
        (re.compile(r"TÊXT|TEXT|TECID|FIAÇÃO|FIACAO|KARSTEN|RENAUX|DOHLER|SANTANENSE|PETTENATI|CEDRO", re.IGNORECASE), "Têxteis"),
        (re.compile(r"FERTILIZ|HERINGER|NUTRIPLANT|VITTIA", re.IGNORECASE), "Fertilizantes"),
        (re.compile(r"PETROQU|BRASKEM|UNIPAR|QUÍMIC|QUIMIC|PIGMENT|DEXXOS|TRONOX|CARBOCLORO|UNIÃO PET", re.IGNORECASE), "Químicos"),
    ],
    "Consumer Non-Durables": [
        (re.compile(r"BEBID|CERVEJ|AMBEV|SUCO|VINHO", re.IGNORECASE), "Bebidas"),
        (re.compile(r"ALIMENT|CARNE|FRIG|LATICIN|LACTE|MARFRIG|JBS|BRF|M.DIAS|MINERVA", re.IGNORECASE), "Alimentos"),
        (re.compile(r"HIGIENE|COSMÉT|COSMET|PERFUM|NATURA|BOTICÁRIO", re.IGNORECASE), "Higiene e Cosméticos"),
        (re.compile(r"TABACO|TABAC|FUMO|SOUZA CRUZ", re.IGNORECASE), "Tabaco"),
        (re.compile(r"VESTU|CALÇADO|CALCADO|ROUPA", re.IGNORECASE), "Vestuário"),
    ],
    "Retail Trade": [
        (re.compile(r"FARMÁCI|FARMACI|DROGA|PAGUE MENOS|RAIA", re.IGNORECASE), "Farmácias"),
        (re.compile(r"SUPERMERC|VAREJO ALIMENT|CARREFOUR|PÃO DE AÇÚCAR|ASSAÍ|ASSAI|GRUPO MATEUS", re.IGNORECASE), "Supermercados"),
        (re.compile(r"ELETRO|MAGAZINE|CASAS BAHIA|VIA VAREJO|LOJAS AMERIC|AMERICANAS", re.IGNORECASE), "Eletrodomésticos e Eletrônicos"),
        (re.compile(r"MATERIAIS DE CONSTRU|CONSTRU E ENGEN|LEROY", re.IGNORECASE), "Materiais de Construção"),
    ],
    "Consumer Services": [
        (re.compile(r"EDUCA|ENSINO|ANIMA|YDUQS|COGNA|CRUZEIRO", re.IGNORECASE), "Educação"),
        (re.compile(r"SAÚDE|SAUDE|HOSPITAL|CLÍNIC|CLINIC|REDE D", re.IGNORECASE), "Saúde"),
        (re.compile(r"VIAGEM|HOTEL|TURISMO|CVC|LAZER", re.IGNORECASE), "Viagens e Lazer"),
        (re.compile(r"RESTAURANT|BK BRASIL|ARCOS", re.IGNORECASE), "Restaurantes"),
        (re.compile(r"MÍDIA|MIDIA|ENTRETEN|CINEMA", re.IGNORECASE), "Mídia"),
    ],
    "Transportation": [
        (re.compile(r"FERROV|RUMO|VLI", re.IGNORECASE), "Ferrovias"),
        (re.compile(r"RODOV|ECORODO|CCR|CONCESS", re.IGNORECASE), "Rodovias"),
        (re.compile(r"AÉREA|AEREA|AZUL|GOL|LATAM", re.IGNORECASE), "Aéreas"),
        (re.compile(r"PORTO|WILSON SONS|SANTOS BRASIL", re.IGNORECASE), "Portos"),
        (re.compile(r"LOGÍSTICA|LOGISTICA|ARMAZEN|JSL|SIMPAR|TEGMA", re.IGNORECASE), "Logística"),
    ],
    "Utilities": [
        (re.compile(r"ENERGIA ELÉTRICA|ENERGIA ELETRICA|ELETROBRAS|EQUATORIAL|ENGIE|ENEVA|CEMIG|COPEL|CPFL|TAESA|NEOENERGIA|ENERGISA|ALUPAR", re.IGNORECASE), "Energia Elétrica"),
        (re.compile(r"SANEAMENTO|ÁGUA|AGUA|SABESP|COPASA|SANEPAR|AEGEA", re.IGNORECASE), "Saneamento"),
        (re.compile(r"GÁS|GAS |COMGAS|ULTRAPAR", re.IGNORECASE), "Gás"),
    ],
    "Producer Manufacturing": [
        (re.compile(r"AUTOPEÇAS|AUTOPECA|MARCOPOLO|RANDON|IOCHPE|TUPY|MAHLE|FRAS-?LE", re.IGNORECASE), "Autopeças"),
        (re.compile(r"MÁQUIN|MAQUIN|WEG|EMBRAER", re.IGNORECASE), "Máquinas e Equipamentos"),
        (re.compile(r"AUTOMÓV|AUTOMOV|VEÍCULO|VEICULO", re.IGNORECASE), "Veículos"),
    ],
    "Health Technology": [
        (re.compile(r"FARMA|PHARMA|BIOMM|HYPERA|BLAU|TEVA", re.IGNORECASE), "Farmacêuticos"),
        (re.compile(r"DIAGNÓSTIC|DIAGNOSTIC|FLEURY|DASA", re.IGNORECASE), "Diagnósticos"),
        (re.compile(r"HOSPITAL|REDE D|QUALICORP|HAPVIDA|NOTREDAME|INTERMÉDICA", re.IGNORECASE), "Hospitais e Planos"),
    ],
}


# Default subsector label when no rule in SUBSECTOR_RULES matches. For sectors
# without a default, falls back to the sector name itself.
SUBSECTOR_DEFAULT = {
    "Finance": "Financeiro",
    "Non-Energy Minerals": "Mineração e Siderurgia",
    "Process Industries": "Processos Industriais",
    "Consumer Non-Durables": "Bens de Consumo",
    "Retail Trade": "Varejo",
    "Consumer Services": "Serviços ao Consumidor",
    "Transportation": "Transporte",
    "Utilities": "Utilidade Pública",
    "Producer Manufacturing": "Manufatura",
    "Health Technology": "Tecnologia em Saúde",
}


# Sectors considered adjacent / contiguous for peer filling when the source
# sector is too small. Asymmetric by design — each entry lists sectors that
# would be reasonable stretch-peers if we can't fill slots with same-sector
# matches alone.
ADJACENT_SECTORS = {
    "Non-Energy Minerals": ["Process Industries", "Producer Manufacturing", "Industrial Services"],
    "Process Industries": ["Non-Energy Minerals", "Consumer Non-Durables", "Producer Manufacturing"],
    "Energy Minerals": ["Utilities", "Industrial Services"],
    "Utilities": ["Energy Minerals", "Industrial Services"],
    "Health Services": ["Health Technology"],
    "Health Technology": ["Health Services"],
    "Technology Services": ["Electronic Technology", "Communications"],
    "Electronic Technology": ["Technology Services", "Producer Manufacturing"],
    "Communications": ["Technology Services"],
    "Retail Trade": ["Consumer Services", "Distribution Services", "Consumer Non-Durables", "Consumer Durables"],
    "Consumer Services": ["Retail Trade", "Consumer Non-Durables"],
    "Distribution Services": ["Retail Trade", "Transportation"],
    "Consumer Non-Durables": ["Consumer Durables", "Retail Trade", "Process Industries"],
    "Consumer Durables": ["Consumer Non-Durables", "Retail Trade", "Producer Manufacturing"],
    "Transportation": ["Industrial Services", "Distribution Services"],
    "Industrial Services": ["Producer Manufacturing", "Transportation"],
    "Producer Manufacturing": ["Industrial Services", "Electronic Technology", "Non-Energy Minerals"],
    "Commercial Services": ["Industrial Services", "Consumer Services"],
}


def get_subsector(name, sector):
    for pattern, subsector in SUBSECTOR_RULES.get(sector, []):
        if pattern.search(name):
            return subsector
    return SUBSECTOR_DEFAULT.get(sector, sector)


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

        # Lazy-fetch sector for US tickers that don't have one yet
        if not current_sector and not is_brazilian_ticker(symbol_upper):
            try:
                profile = fetch_profile(symbol_upper)
                if profile and profile.get("sector"):
                    current_sector = profile["sector"]
                    Ticker.objects.filter(symbol=symbol_upper).update(sector=current_sector)
            except FMPError:
                pass

        if not current_sector:
            result = []
        else:
            adjacent_sectors = ADJACENT_SECTORS.get(current_sector, [])
            candidate_sectors = [current_sector, *adjacent_sectors]
            all_candidate_tickers = list(
                Ticker.objects.filter(type="stock", sector__in=candidate_sectors)
                .exclude(symbol__regex=r"^[A-Z]+\d+F$")
                .values("symbol", "name", "display_name", "sector", "market_cap")
            )
            for ticker in all_candidate_tickers:
                ticker["name"] = ticker.pop("display_name") or ticker["name"]

            current_subsector = get_subsector(current_name, current_sector)
            source_is_brazilian = is_brazilian_ticker(symbol_upper)

            def sector_tier(peer):
                # 0 = same subsector & same sector (closest peers)
                # 1 = different subsector but same sector
                # 2 = adjacent sector (stretch peer)
                if peer["sector"] != current_sector:
                    return 2
                if get_subsector(peer["name"], peer["sector"]) == current_subsector:
                    return 0
                return 1

            def peer_sort_key(peer):
                peer_is_brazilian = is_brazilian_ticker(peer["symbol"])
                same_country = peer_is_brazilian == source_is_brazilian
                market_cap = peer.get("market_cap")
                has_market_cap = market_cap is not None
                return (
                    sector_tier(peer),
                    0 if same_country else 1,
                    0 if has_market_cap else 1,
                    -(market_cap or 0),
                )

            candidates = [
                t for t in all_candidate_tickers
                if ticker_base(t["symbol"]) != current_base
            ]
            peers = sorted(
                deduplicate_by_company(candidates), key=peer_sort_key,
            )[:self.MAX_PEERS]
            result = [{"symbol": p["symbol"], "name": p["name"]} for p in peers]

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

        # Symbol prefix matches. Rank the exact-symbol row (if any) ahead of
        # longer siblings so it survives the MAX_SYMBOL_MATCHES cap even when
        # its market_cap is NULL.
        exact_symbol_priority = Case(
            When(symbol__iexact=query_upper, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
        symbol_matches = list(
            Ticker.objects.filter(type="stock", symbol__istartswith=query_upper)
            .exclude(symbol__regex=exclude_fractional)
            .order_by(exact_symbol_priority, market_cap_ordering)
            .values(*fields)
            [:self.MAX_SYMBOL_MATCHES]
        )

        # Name and alias matches (always fetched to blend in popular companies,
        # and to surface tickers whose current display_name no longer contains
        # the phrase users still search for — e.g. "General Electric" → GE).
        found_symbols = {r["symbol"] for r in symbol_matches}
        name_slots = max(self.MIN_NAME_SLOTS, self.SEARCH_LIMIT - len(symbol_matches))
        name_matches = list(
            Ticker.objects.filter(type="stock")
            .filter(Q(display_name__icontains=query) | Q(aliases__icontains=query))
            .exclude(symbol__in=found_symbols)
            .exclude(symbol__regex=exclude_fractional)
            .order_by(market_cap_ordering)
            .values(*fields)
            [:name_slots]
        )

        # Merge by relevance bucket first, then market cap. Buckets:
        #   0 = exact symbol match, 1 = symbol prefix match, 2 = name contains.
        # Within a bucket, larger market caps win and NULLs sort last.
        def relevance_key(row):
            symbol = row["symbol"].upper()
            if symbol == query_upper:
                bucket = 0
            elif symbol.startswith(query_upper):
                bucket = 1
            else:
                bucket = 2
            market_cap = row["market_cap"]
            return (bucket, market_cap is None, -(market_cap or 0))

        results = symbol_matches + name_matches
        results.sort(key=relevance_key)
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


def _persist_snapshot_from_view(
    ticker: str,
    market_cap: int,
    current_price: Decimal,
    pe10_result: dict,
    pfcf10_result: dict,
    leverage_result: dict,
    peg_result: dict,
    pfcf_peg_result: dict,
    debt_to_avg_earnings,
    debt_to_avg_fcf,
) -> None:
    """Cache the user-viewed indicator set into ``IndicatorSnapshot`` and keep
    ``Ticker.market_cap`` in sync.

    Called as a side-effect at the end of :class:`PE10View.get`. Any write
    failure is swallowed — persistence must never break the page.
    """

    def _to_decimal(value):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    try:
        IndicatorSnapshot.objects.update_or_create(
            ticker=ticker,
            defaults={
                "pe10": _to_decimal(pe10_result.get("pe10")),
                "pfcf10": _to_decimal(pfcf10_result.get("pfcf10")),
                "peg": _to_decimal(peg_result.get("peg")),
                "pfcf_peg": _to_decimal(pfcf_peg_result.get("pfcfPeg")),
                "debt_to_equity": _to_decimal(leverage_result.get("debtToEquity")),
                "debt_ex_lease_to_equity": _to_decimal(
                    leverage_result.get("debtExLeaseToEquity"),
                ),
                "liabilities_to_equity": _to_decimal(
                    leverage_result.get("liabilitiesToEquity"),
                ),
                "current_ratio": _to_decimal(leverage_result.get("currentRatio")),
                "debt_to_avg_earnings": _to_decimal(debt_to_avg_earnings),
                "debt_to_avg_fcf": _to_decimal(debt_to_avg_fcf),
                "market_cap": int(market_cap) if market_cap else None,
                "current_price": _to_decimal(current_price),
            },
        )
    except Exception as error:
        logger.warning("IndicatorSnapshot persist failed for %s: %s", ticker, error)

    try:
        Ticker.objects.filter(symbol=ticker).update(market_cap=int(market_cap))
    except Exception as error:
        logger.warning("Ticker.market_cap persist failed for %s: %s", ticker, error)


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
            snapshot = IndicatorSnapshot.objects.filter(ticker=ticker).first()
            if snapshot:
                if not market_cap and snapshot.market_cap:
                    market_cap = int(snapshot.market_cap)
                if not current_price and snapshot.current_price:
                    current_price = Decimal(str(snapshot.current_price))

        if not market_cap or not current_price:
            return Response(
                {"error": "Dados de mercado indisponíveis para este ticker."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        market_cap_decimal = Decimal(str(market_cap))

        # Get logo + reported currency from Ticker table.
        logo = ""
        reported_currency = ""
        try:
            ticker_row = Ticker.objects.values("logo", "reported_currency").get(symbol=ticker)
            logo = ticker_row["logo"]
            reported_currency = ticker_row["reported_currency"]
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

        listing_currency = "BRL" if is_brazilian_ticker(ticker) else "USD"
        result = {
            "ticker": ticker,
            "name": name,
            "logo": logo,
            "currentPrice": float(current_price),
            "marketCap": market_cap,
            "listingCurrency": listing_currency,
            "reportedCurrency": reported_currency or listing_currency,
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

        # Warm the screener snapshot + refresh Ticker.market_cap as a side-effect
        # of the user view. Wrapped in a broad try/except so any bug in the
        # persist path (DB outage, schema drift, etc.) never breaks the page.
        try:
            _persist_snapshot_from_view(
                ticker=ticker,
                market_cap=market_cap,
                current_price=current_price,
                pe10_result=pe10_result,
                pfcf10_result=pfcf10_result,
                leverage_result=leverage_result,
                peg_result=peg_result,
                pfcf_peg_result=pfcf_peg_result,
                debt_to_avg_earnings=debt_to_avg_earnings,
                debt_to_avg_fcf=debt_to_avg_fcf,
            )
        except Exception as error:
            logger.warning("persist_snapshot_from_view failed for %s: %s", ticker, error)

        cache.set(cache_key, result, PE10_CACHE_TTL)
        return Response(result)


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

        cache_key = f"multiples_history:{ticker}"
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

        current_price = float(quote.get("regularMarketPrice", 0))
        market_cap = quote.get("marketCap")

        if not market_cap or not current_price:
            snapshot = IndicatorSnapshot.objects.filter(ticker=ticker).first()
            if snapshot:
                if not market_cap and snapshot.market_cap:
                    market_cap = int(snapshot.market_cap)
                if not current_price and snapshot.current_price:
                    current_price = float(snapshot.current_price)

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

        cache.set(cache_key, result, MULTIPLES_HISTORY_CACHE_TTL)
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

        if not market_cap or not current_price:
            snapshot = IndicatorSnapshot.objects.filter(ticker=ticker).first()
            if snapshot:
                if not market_cap and snapshot.market_cap:
                    market_cap = int(snapshot.market_cap)
                if not current_price and snapshot.current_price:
                    current_price = float(snapshot.current_price)

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
        quarterly_ratios = compute_quarterly_balance_ratios(ticker)

        listing_currency = "BRL" if is_brazilian_ticker(ticker) else "USD"
        reported_currency = (
            Ticker.objects.filter(symbol=ticker).values_list("reported_currency", flat=True).first() or ""
        )
        result = {
            "years": fundamentals,
            "quarterlyRatios": quarterly_ratios,
            "listingCurrency": listing_currency,
            "reportedCurrency": reported_currency or listing_currency,
        }
        cache.set(cache_key, result, FUNDAMENTALS_CACHE_TTL)
        response = Response(result)
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
# After all sources fail for a symbol, remember the miss for this long so we
# don't re-hit BRAPI / the network on every request. Short enough that a newly
# published logo still surfaces within a day.
LOGO_NEGATIVE_CACHE_TTL = 24 * 3600
BRAPI_LOGO_URL_TEMPLATE = "https://icons.brapi.dev/icons/{symbol}.svg"


def detect_image_content_type(data: bytes) -> str:
    """Detect image content type from file magic bytes."""
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if b"<svg" in data[:256]:
        return "image/svg+xml"
    return "image/png"


def is_brapi_placeholder(image_data: bytes) -> bool:
    """Detect whether an SVG is the BRAPI branding placeholder, not a real logo."""
    if b"<svg" not in image_data[:256]:
        return False
    return b"brapi.dev" in image_data or b"<title>brapi</title>" in image_data


def generate_fallback_svg(symbol: str) -> bytes:
    """Generate a simple colored-circle SVG with the ticker's first letter."""
    letter = symbol[0] if symbol else "?"
    # Deterministic color from symbol hash
    color_hash = hashlib.md5(symbol.encode()).hexdigest()[:6]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">'
        f'<circle cx="28" cy="28" r="28" fill="#{color_hash}"/>'
        f'<text x="28" y="29" text-anchor="middle" dominant-baseline="central" '
        f'font-family="Arial,sans-serif" font-size="24" font-weight="bold" fill="#fff">'
        f"{letter}</text></svg>"
    ).encode()


def _fetch_logo(url: str) -> bytes | None:
    """Fetch logo data from a URL. Returns None on failure."""
    try:
        logo_request = Request(url, headers={"User-Agent": "Sponda/1.0"})
        with urlopen(logo_request, timeout=10) as logo_response:
            return logo_response.read()
    except Exception:
        return None


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

        # Serve from disk cache (but purge BRAPI placeholders that slipped in)
        if cached_path.exists():
            image_data = cached_path.read_bytes()
            if is_brapi_placeholder(image_data):
                cached_path.unlink()
            else:
                content_type = detect_image_content_type(image_data)
                response = HttpResponse(image_data, content_type=content_type)
                response["Cache-Control"] = f"public, max-age={LOGO_CACHE_MAX_AGE}"
                return response

        # Short-circuit: if we recently confirmed no real logo exists, skip all
        # network work and serve the generated fallback immediately.
        negative_cache_key = f"logo_miss:{symbol}"
        if cache.get(negative_cache_key):
            return self._fallback_response(symbol)

        image_data = self._resolve_logo_bytes(symbol)

        if image_data:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached_path.write_bytes(image_data)
            content_type = detect_image_content_type(image_data)
            response = HttpResponse(image_data, content_type=content_type)
            response["Cache-Control"] = f"public, max-age={LOGO_CACHE_MAX_AGE}"
            return response

        # All sources failed — mark as a miss so we stop re-fetching on every request.
        cache.set(negative_cache_key, True, LOGO_NEGATIVE_CACHE_TTL)
        logger.warning("No logo available for %s, serving fallback", symbol)
        return self._fallback_response(symbol)

    def _resolve_logo_bytes(self, symbol: str) -> bytes | None:
        """Walk the resolution chain and return real logo bytes, or None."""
        candidate_urls: list[str] = []

        override_url = LOGO_OVERRIDE_URLS.get(symbol)
        if override_url:
            candidate_urls.append(override_url)

        try:
            ticker = Ticker.objects.get(symbol=symbol)
        except Ticker.DoesNotExist:
            ticker = None

        if ticker and ticker.logo and not is_placeholder_logo_url(ticker.logo):
            candidate_urls.append(ticker.logo)

        candidate_urls.append(BRAPI_LOGO_URL_TEMPLATE.format(symbol=symbol))

        seen: set[str] = set()
        for url in candidate_urls:
            if url in seen:
                continue
            seen.add(url)
            image_data = _fetch_logo(url)
            if image_data and not is_brapi_placeholder(image_data):
                return image_data
        return None

    def _fallback_response(self, symbol: str) -> HttpResponse:
        fallback_data = generate_fallback_svg(symbol)
        response = HttpResponse(fallback_data, content_type="image/svg+xml")
        response["Cache-Control"] = "public, max-age=3600"
        return response


# Locales mirrored here must stay in sync with
# frontend/src/lib/i18n-config.ts::SUPPORTED_LOCALES.
SITEMAP_LOCALES = ("en", "pt", "es", "zh", "fr", "de", "it")

# hreflang tags per locale — mirrors LOCALE_TO_HTML_LANG on the frontend.
SITEMAP_HREFLANG = {
    "en": "en",
    "pt": "pt-BR",
    "es": "es",
    "zh": "zh-CN",
    "fr": "fr",
    "de": "de",
    "it": "it",
}

# x-default points at English, matching the frontend alternates.
SITEMAP_X_DEFAULT_LOCALE = "en"

# Canonical tab key → localized URL slug per locale.
# Mirrors frontend/src/middleware.ts::CANONICAL_TO_LOCALE_SLUG.
SITEMAP_TAB_SLUGS = {
    "charts":       {"en": "charts", "pt": "graficos", "es": "graficos", "zh": "charts",
                     "fr": "graphiques", "de": "diagramme", "it": "grafici"},
    "fundamentals": {"en": "fundamentals", "pt": "fundamentos", "es": "fundamentos", "zh": "fundamentals",
                     "fr": "fondamentaux", "de": "fundamentaldaten", "it": "fondamentali"},
    "compare":      {"en": "compare", "pt": "comparar", "es": "comparar", "zh": "compare",
                     "fr": "comparer", "de": "vergleich", "it": "confronta"},
}


def _sitemap_url_group(base_url, path_builder, priority, changefreq, lastmod=""):
    """Emit one <url> entry per locale, each with hreflang alternates for all locales.

    `path_builder(locale)` returns the path segment after the locale prefix,
    e.g. "" for the homepage or "/PETR4/fundamentos" for a ticker tab.
    """
    lines = []
    # Pre-compute every locale's absolute URL so we can reuse them as
    # xhtml:link alternates inside each per-locale <url> block.
    locale_urls = {loc: f"{base_url}/{loc}{path_builder(loc)}" for loc in SITEMAP_LOCALES}
    for locale in SITEMAP_LOCALES:
        lines.append("  <url>")
        lines.append(f"    <loc>{locale_urls[locale]}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        for alt_locale in SITEMAP_LOCALES:
            hreflang = SITEMAP_HREFLANG[alt_locale]
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="{hreflang}" '
                f'href="{locale_urls[alt_locale]}" />'
            )
        lines.append(
            f'    <xhtml:link rel="alternate" hreflang="x-default" '
            f'href="{locale_urls[SITEMAP_X_DEFAULT_LOCALE]}" />'
        )
        lines.append("  </url>")
    return lines


class SitemapView(APIView):
    """Generate a dynamic XML sitemap with locale-prefixed URLs and hreflang alternates.

    Every page (homepage, ticker root, ticker tabs) is emitted once per supported
    locale, with xhtml:link rel="alternate" entries advertising the other locale
    variants. This mirrors the Next.js frontend's `alternates.languages` metadata
    so search engines can index each locale and serve the right variant by region.
    """

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
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        ]

        # Homepage: one <url> per locale, each with full hreflang alternates.
        lines.extend(_sitemap_url_group(
            base_url,
            path_builder=lambda _locale: "",
            priority="1.0",
            changefreq="daily",
        ))

        # Per-ticker URL groups: root, fundamentals, charts, compare.
        ticker_groups = [
            (None,           "0.8", "weekly"),
            ("fundamentals", "0.6", "weekly"),
            ("charts",       "0.5", "weekly"),
            ("compare",      "0.4", "monthly"),
        ]

        for symbol, updated_at in tickers:
            lastmod = updated_at.strftime("%Y-%m-%d") if updated_at else ""
            for tab_key, priority, changefreq in ticker_groups:
                if tab_key is None:
                    path_builder = lambda _locale, s=symbol: f"/{s}"
                else:
                    slug_map = SITEMAP_TAB_SLUGS[tab_key]
                    path_builder = lambda locale, s=symbol, m=slug_map: f"/{s}/{m[locale]}"
                lines.extend(_sitemap_url_group(
                    base_url, path_builder, priority, changefreq, lastmod,
                ))

        lines.append("</urlset>")

        xml = "\n".join(lines)
        response = HttpResponse(xml, content_type="application/xml")
        response["Cache-Control"] = "public, max-age=86400"
        return response


# ---------------------------------------------------------------------------
# Screener
# ---------------------------------------------------------------------------

# Numeric indicator fields the screener can filter by. Explicit allow-list so
# unknown query params are ignored safely. Market cap is deliberately excluded —
# users rank by it (default sort) and read it in the results, but shouldn't
# screen by it as a min/max bound.
SCREENER_FILTERABLE_FIELDS = (
    "pe10",
    "pfcf10",
    "peg",
    "pfcf_peg",
    "debt_to_equity",
    "debt_ex_lease_to_equity",
    "liabilities_to_equity",
    "current_ratio",
    "debt_to_avg_earnings",
    "debt_to_avg_fcf",
)

# Sortable set is the filterable set plus market_cap (for the default ranking)
# and ticker (alphabetical). Kept as a separate constant so the filter/sort
# surfaces can diverge without tangling.
SCREENER_SORTABLE_FIELDS = SCREENER_FILTERABLE_FIELDS + ("market_cap", "ticker")
SCREENER_DEFAULT_SORT = "ticker"
SCREENER_DEFAULT_LIMIT = 50
SCREENER_MAX_LIMIT = 500


def _parse_decimal_param(raw_value: str, field_name: str) -> Decimal:
    """Parse a query-string numeric bound, raising ValueError on garbage input."""
    try:
        return Decimal(raw_value)
    except (ArithmeticError, ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {field_name}: {raw_value!r}")


class ScreenerView(APIView):
    """Filter the IndicatorSnapshot table by ratio thresholds.

    Query parameters (all optional):
      * ``<field>_min`` / ``<field>_max`` — numeric bounds on any indicator in
        :data:`SCREENER_FILTERABLE_FIELDS`. Rows whose value is ``NULL`` are
        excluded from the filter (cannot prove they satisfy the threshold).
      * ``sort`` — one of :data:`SCREENER_SORTABLE_FIELDS`, optionally prefixed
        with ``-`` for descending. Defaults to ``ticker`` ascending.
      * ``limit`` — max rows returned (default 50, hard-capped at 500).
      * ``offset`` — rows to skip before returning (for pagination).

    Response shape::

        {
            "count": <total matching rows>,
            "results": [
                {"ticker": ..., "name": ..., "sector": ..., "logo": ...,
                 "market_cap": ..., "current_price": ...,
                 "pe10": ..., "pfcf10": ..., ...},
                ...
            ],
        }
    """

    def get(self, request):
        queryset = IndicatorSnapshot.objects.all()

        # Apply numeric min/max filters ---------------------------------------
        for field in SCREENER_FILTERABLE_FIELDS:
            for suffix, lookup in (("_min", "gte"), ("_max", "lte")):
                raw_value = request.query_params.get(f"{field}{suffix}")
                if raw_value is None or raw_value == "":
                    continue
                try:
                    value = _parse_decimal_param(raw_value, f"{field}{suffix}")
                except ValueError as exc:
                    return Response(
                        {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST,
                    )
                queryset = queryset.filter(**{f"{field}__{lookup}": value})

        total_count = queryset.count()

        # Sort ----------------------------------------------------------------
        sort_param = request.query_params.get("sort") or SCREENER_DEFAULT_SORT
        sort_field = sort_param.lstrip("-")
        if sort_field not in SCREENER_SORTABLE_FIELDS:
            return Response(
                {"error": f"Invalid sort field: {sort_param!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Nulls-last on DESC so rows with missing data don't dominate the top.
        queryset = queryset.order_by(
            F(sort_field).desc(nulls_last=True)
            if sort_param.startswith("-")
            else F(sort_field).asc(nulls_last=True),
            "ticker",
        )

        # Paginate ------------------------------------------------------------
        try:
            limit = int(request.query_params.get("limit", SCREENER_DEFAULT_LIMIT))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"error": "limit and offset must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit = max(1, min(limit, SCREENER_MAX_LIMIT))
        offset = max(0, offset)
        page = list(queryset[offset:offset + limit])

        # Hydrate ticker metadata in one query so the response is fully
        # self-contained for the frontend table.
        ticker_symbols = [snapshot.ticker for snapshot in page]
        ticker_metadata = {
            row["symbol"]: row
            for row in Ticker.objects.filter(symbol__in=ticker_symbols).values(
                "symbol", "name", "display_name", "sector", "logo",
            )
        }

        results = []
        for snapshot in page:
            metadata = ticker_metadata.get(snapshot.ticker, {})
            results.append({
                "ticker": snapshot.ticker,
                "name": metadata.get("display_name") or metadata.get("name") or "",
                "sector": metadata.get("sector") or "",
                "logo": metadata.get("logo") or "",
                "pe10": snapshot.pe10,
                "pfcf10": snapshot.pfcf10,
                "peg": snapshot.peg,
                "pfcf_peg": snapshot.pfcf_peg,
                "debt_to_equity": snapshot.debt_to_equity,
                "debt_ex_lease_to_equity": snapshot.debt_ex_lease_to_equity,
                "liabilities_to_equity": snapshot.liabilities_to_equity,
                "current_ratio": snapshot.current_ratio,
                "debt_to_avg_earnings": snapshot.debt_to_avg_earnings,
                "debt_to_avg_fcf": snapshot.debt_to_avg_fcf,
                "market_cap": snapshot.market_cap,
                "current_price": snapshot.current_price,
            })

        return Response({"count": total_count, "results": results})
