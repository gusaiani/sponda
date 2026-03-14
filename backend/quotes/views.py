from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .brapi import BRAPIError, fetch_quote, sync_earnings
from .models import LookupLog, QuarterlyEarnings
from .pe10 import calculate_pe10


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
        name = quote.get("longName") or quote.get("shortName") or ticker

        # Derive shares outstanding from marketCap / price for EPS fallback
        shares_outstanding = None
        market_cap = quote.get("marketCap")
        if market_cap and current_price:
            shares_outstanding = Decimal(str(market_cap)) / current_price

        # Calculate PE10
        result = calculate_pe10(ticker, current_price, shares_outstanding)

        # Log the lookup
        self._log_lookup(request, ticker)

        return Response({
            "ticker": ticker,
            "name": name,
            "pe10": result["pe10"],
            "currentPrice": float(current_price),
            "marketCap": market_cap,
            "avgAdjustedEPS": result["avg_adjusted_eps"],
            "yearsOfData": result["years_of_data"],
            "label": result["label"],
            "error": result["error"],
            "annualData": result["annual_data"],
            "calculationDetails": result["calculation_details"],
            "_version": "2026-03-14a",
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
        has_fresh = QuarterlyEarnings.objects.filter(
            ticker=ticker, fetched_at__gte=cutoff
        ).exists()

        if not has_fresh:
            try:
                sync_earnings(ticker)
            except BRAPIError:
                pass  # Use whatever cached data we have
