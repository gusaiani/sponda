"""Write a request's provider accounting once, when the request ends.

Every outbound FMP call adds to a per-endpoint ledger
(`quotes.provider_usage`). A cold company page makes one call per
statement, and a write per call showed up in Sentry as an N+1 on the quote
endpoints. This middleware opens one batch per request, so the request
pays for a single insert-or-increment however many calls it made.
"""
from quotes.provider_usage import batched_provider_usage


class ProviderUsageBatchMiddleware:
    """Sums the request's provider calls and writes them in one statement."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with batched_provider_usage():
            return self.get_response(request)
