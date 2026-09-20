"""Cap how long provider pacing may block a request.

`quotes.rate_limiter` waits for the outbound allowance to refill, which is
right for a Celery task or a management command: nothing is timing them,
and waiting is cheaper than a 429 that spends the data allowance anyway.

A request is different. Gunicorn aborts a worker whose request outlives
the worker timeout, and the abort takes down every other request that
worker was holding, not just the slow one. Sentry caught exactly that on
`/api/quote/{ticker}/`: a 36-second wait for the FMP window to roll over,
ended by `SystemExit: 1` from gunicorn's `handle_abort`.

So a request gets a budget it can afford, and a wait longer than that
becomes an ordinary provider error the views already degrade on.
"""
from django.conf import settings

from quotes.rate_limiter import wait_budget


class ProviderWaitBudgetMiddleware:
    """Gives each request a ceiling on time spent waiting for pacing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with wait_budget(settings.PROVIDER_WAIT_BUDGET_SECONDS):
            return self.get_response(request)
