import pytest

from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model

from assistant.context import build_company_context
from accounts.models import CompanyVisit, IndicatorAlert


class TestBuildCompanyContext:
    def test_wraps_payload_in_company_data_delimiters(self):
        """Prompt-injection defense: everything the LLM is handed as 'data'
        must sit inside <COMPANY_DATA>…</COMPANY_DATA> so the system prompt
        can tell the model to treat it strictly as data, never instructions.
        """
        # Real payload keys: the quote payload exposes `name`, not
        # `display_name` (the context layer relabels it for the LLM).
        fake_payload = {"name": "Petróleo Brasileiro", "pe10": 4.2}

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="metrics",
                locale="pt",
                user=None,
            )

        assert context.startswith("<COMPANY_DATA>")
        assert context.rstrip().endswith("</COMPANY_DATA>")
        assert "PETR4" in context
        assert "Petróleo Brasileiro" in context

    def test_includes_key_indicators_and_strips_verbose_blocks(self):
        """The LLM needs the actual numbers it will reason about.

        Cost defense: verbose *CalculationDetails* dicts are intentionally
        excluded — they balloon the prompt and the LLM doesn't need them
        to answer a valuation question.
        """
        # Real payload keys (camelCase): `currentPrice`, plus the verbose
        # *CalculationDetails* dict that must never leak into the prompt.
        fake_payload = {
            "name": "Petróleo Brasileiro",
            "pe10": 4.2,
            "pfcf10": 3.1,
            "peg": 0.8,
            "currentPrice": 38.5,
            "pe10CalculationDetails": {"intermediate": "noise…"},   # must NOT leak
        }

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="metrics",
                locale="pt",
                user=None,
            )

        assert "pe10: 4.2" in context
        assert "pfcf10: 3.1" in context
        assert "peg: 0.8" in context
        assert "current_price: 38.5" in context
        # Cost defense: verbose calc-details blocks must NOT appear in the
        # prompt. The allowlist of named fields guarantees this by construction.
        assert "calculation_details" not in context.lower()
        assert "intermediate" not in context

    @pytest.mark.django_db
    def test_includes_authed_users_note_and_alerts(self):
        """Authed users get their own visit note + active alerts in the prompt.

        Lets the model answer 'what did I note last time?' and 'do I have
        alerts on this?' without the frontend round-tripping the data back.
        Anonymous requests (user=None) never see personal data — covered by
        the earlier tests in this class.
        """
        User = get_user_model()
        user = User.objects.create_user(
            username="g@example.com",
            email="g@example.com",
            password="pw123456",
        )
        CompanyVisit.objects.create(
            user=user,
            ticker="PETR4",
            note="Watching the dividend payout ratio.",
        )
        IndicatorAlert.objects.create(
            user=user,
            ticker="PETR4",
            indicator="pe10",
            comparison=IndicatorAlert.COMPARISON_LTE,
            threshold=Decimal("5"),
        )

        fake_payload = {"display_name": "Petróleo Brasileiro"}

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="metrics",
                locale="pt",
                user=user,
            )

        assert "your_note: Watching the dividend payout ratio." in context
        assert "your_alert: pe10 lte 5" in context

    def test_fundamentals_tab_adds_balance_sheet_fields(self):
        """The data block follows the open tab. On the fundamentals tab the
        model should see the leverage / balance-sheet numbers the user is
        looking at, so it can answer about debt without the client resending
        what the server already computed.
        """
        fake_payload = {
            "name": "Petróleo Brasileiro",
            "pe10": 4.2,
            "debtToEquity": 0.85,
            "currentRatio": 1.4,
            "totalDebt": 300_000,
        }

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="fundamentals",
                locale="pt",
                user=None,
            )

        assert "debt_to_equity: 0.85" in context
        assert "current_ratio: 1.4" in context
        assert "total_debt: 300000" in context

    def test_metrics_tab_omits_fundamentals_only_fields(self):
        """Tab scoping is exclusive: a balance-sheet field offered only on the
        fundamentals tab must NOT appear on the metrics tab, so every prompt
        carries just the numbers on screen, not the whole payload.
        """
        fake_payload = {
            "name": "Petróleo Brasileiro",
            "pe10": 4.2,
            "debtToEquity": 0.85,
        }

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="metrics",
                locale="pt",
                user=None,
            )

        # Base fields always present...
        assert "pe10: 4.2" in context
        # ...but the fundamentals-only field is scoped out.
        assert "debt_to_equity" not in context

    def test_recomputes_multiples_for_the_users_window(self):
        """The assistant must reason over the SAME window the user is viewing
        (the PRAZO slider). The window threads into the canonical calc
        functions so pe10/pfcf10/peg match the on-screen numbers, not the
        backend's all-history default (the 66.66-vs-49.9 bug).
        """
        fake_payload = {"name": "WEG", "marketCap": 1000, "totalDebt": 50}

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ), patch(
            "assistant.context.calculate_pe10",
            return_value={"pe10": 49.9, "avg_adjusted_net_income": 20},
        ) as pe10_calc, patch(
            "assistant.context.calculate_pfcf10",
            return_value={"pfcf10": 76.8, "avg_adjusted_fcf": 13},
        ), patch(
            "assistant.context.calculate_peg",
            return_value={"peg": 2.0, "earningsCAGR": 24.9},
        ), patch(
            "assistant.context.calculate_pfcf_peg",
            return_value={"pfcfPeg": 4.14, "fcfCAGR": 18.6},
        ):
            context = build_company_context(
                ticker="WEGE3",
                tab="metrics",
                locale="pt",
                user=None,
                years=10,
            )

        # The window flowed into the canonical calc, and its result — not the
        # payload's all-history scalar — is what reaches the prompt.
        assert pe10_calc.call_args.kwargs["max_years"] == 10
        assert "pe10: 49.9" in context
        assert "pfcf10: 76.8" in context

    def test_recomputes_windowed_debt_coverage_on_fundamentals_tab(self):
        """Debt-coverage ratios are window-dependent (they divide by the
        windowed average earnings/FCF), so they too must be recomputed for the
        user's window, not read from the all-history payload.
        """
        fake_payload = {"name": "WEG", "marketCap": 1000, "totalDebt": 60}

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ), patch(
            "assistant.context.calculate_pe10",
            return_value={"pe10": 49.9, "avg_adjusted_net_income": 20},
        ), patch(
            "assistant.context.calculate_pfcf10",
            return_value={"pfcf10": 76.8, "avg_adjusted_fcf": 15},
        ), patch(
            "assistant.context.calculate_peg",
            return_value={"peg": 2.0, "earningsCAGR": 24.9},
        ), patch(
            "assistant.context.calculate_pfcf_peg",
            return_value={"pfcfPeg": 4.14, "fcfCAGR": 18.6},
        ):
            context = build_company_context(
                ticker="WEGE3",
                tab="fundamentals",
                locale="pt",
                user=None,
                years=5,
            )

        # 60 / 20 = 3.0 ; 60 / 15 = 4.0
        assert "debt_to_avg_earnings: 3.0" in context
        assert "debt_to_avg_fcf: 4.0" in context

    def test_without_window_does_not_recompute(self):
        """No window (assistant invoked off a company page, or a legacy
        client) → fall back to the canonical payload scalars rather than
        recomputing. Keeps the path backward-compatible.
        """
        with patch(
            "assistant.context._compute_quote_payload",
            return_value={"name": "WEG", "pe10": 66.66},
        ), patch("assistant.context.calculate_pe10") as pe10_calc:
            context = build_company_context(
                ticker="WEGE3",
                tab="metrics",
                locale="pt",
                user=None,
            )

        pe10_calc.assert_not_called()
        assert "pe10: 66.66" in context

    def test_truncates_oversized_payload(self):
        """A pathological payload (e.g. a runaway string field, future bloat)
        cannot blow the context window or the per-call cost.

        Truncation must preserve the closing </COMPANY_DATA> delimiter,
        otherwise the prompt-injection boundary breaks and the model could
        treat whatever bled in next as instructions.
        """
        from assistant.context import MAX_CONTEXT_CHARS

        huge_value = "x" * 20_000
        fake_payload = {"name": huge_value}

        with patch(
            "assistant.context._compute_quote_payload",
            return_value=fake_payload,
        ):
            context = build_company_context(
                ticker="PETR4",
                tab="metrics",
                locale="pt",
                user=None,
            )

        assert len(context) <= MAX_CONTEXT_CHARS
        assert "[truncated]" in context
        # Delimiter MUST survive — see docstring.
        assert context.rstrip().endswith("</COMPANY_DATA>")