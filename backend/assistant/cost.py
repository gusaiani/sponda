"""Token → USD cost calculation for OpenAI model usage.

Prices are per 1,000,000 tokens, from OpenAI's published pricing. This is
the single source of truth so LLMQuery.cost_usd and any cost dashboard
never disagree. Decimal — not float — because this becomes a DB money value.
"""
from decimal import Decimal

# USD fer 1,000,000 tokens, keyed by model then by direction.
MODEL_PRICES = {
    "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
}

# Published prices are quoted per this many tokens
TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Return the USD cost of one OpenAI call as a Decimal."""
    prices = MODEL_PRICES[model]
    input_cost = prices["input"] * input_tokens / TOKENS_PER_PRICE_UNIT;
    output_cost = prices["output"] * output_tokens / TOKENS_PER_PRICE_UNIT;
    return input_cost + output_cost