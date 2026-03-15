from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .brapi import BRAPIError, fetch_quote, sync_balance_sheets, sync_cash_flows, sync_earnings
from .leverage import calculate_leverage
from .models import BalanceSheet, LookupLog, QuarterlyCashFlow, QuarterlyEarnings, Ticker
from .pe10 import calculate_pe10
from .peg import calculate_peg
from .pfcf10 import calculate_pfcf10
from .pfcf_peg import calculate_pfcf_peg


import re


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


class TickerListView(APIView):
    def get(self, request):
        tickers = Ticker.objects.filter(type="stock").exclude(symbol__regex=r"^[A-Z]+\d+F$").values("symbol", "name", "sector", "type", "logo")
        response = Response(list(tickers))
        response["Cache-Control"] = "public, max-age=3600"
        return response


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class PE10View(APIView):
    def get(self, request, ticker):
        ticker = ticker.upper()

        # Ensure we have fresh data (< 24h old)
        self._ensure_fresh_data(ticker)

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

        # Calculate metrics
        pe10_result = calculate_pe10(ticker, market_cap_decimal)
        pfcf10_result = calculate_pfcf10(ticker, market_cap_decimal)
        leverage_result = calculate_leverage(ticker)
        peg_result = calculate_peg(ticker, pe10_result["pe10"])
        pfcf_peg_result = calculate_pfcf_peg(ticker, pfcf10_result["pfcf10"])

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

    def _check_rate_limit(self, request):
        limit = settings.SPONDA_FREE_LOOKUPS_PER_DAY
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if request.user.is_authenticated:
            count = LookupLog.objects.filter(
                user=request.user, timestamp__gte=today_start
            ).count()
        else:
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            count = LookupLog.objects.filter(
                session_key=session_key, timestamp__gte=today_start
            ).count()

        if count >= limit:
            return Response(
                {
                    "error": "Daily lookup limit reached. Sign up for more lookups.",
                    "limit": limit,
                    "used": count,
                },
                status=status.HTTP_403_FORBIDDEN,
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

    def _ensure_fresh_data(self, ticker):
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
