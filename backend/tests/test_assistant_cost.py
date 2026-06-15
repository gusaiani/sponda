"""Tests for token → USD cost calculation."""
from decimal import Decimal

from assistant.cost import calculate_cost


class TestCalculateCost:
    def test_gpt_4o_combines_input_and_output_cost(self):
        # 1000 input @ $2.50/1M  +  500 output @ $10.00/1M
        #   = 0.0025 + 0.005 = 0.0075
        cost = calculate_cost("gpt-4o", input_tokens=1_000, output_tokens=500)
        assert cost == Decimal("0.0075")

    def test_gpt_4o_mini_is_cheaper(self):
        # 1000 input @ $0.15/1M  +  500 output @ $0.60/1M
        #   = 0.00015 + 0.0003 = 0.00045
        cost = calculate_cost("gpt-4o-mini", input_tokens=1_000, output_tokens=500)
        assert cost == Decimal("0.00045")

    def test_zero_tokens_is_zero_cost(self):
        assert calculate_cost("gpt-4o", 0, 0) == Decimal("0")