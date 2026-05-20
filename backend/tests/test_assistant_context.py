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
        fake_payload = {"display_name": "Petróleo Brasileiro", "pe10": 4.2}

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
        fake_payload = {
            "display_name": "Petróleo Brasileiro",
            "pe10": 4.2,
            "pfcf10": 3.1,
            "peg": 0.8,
            "current_price": 38.5,
            "pe10_calculation_details": {"intermediate": "noise…"},   # must NOT leak
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
        # Cost defense: verbose calc-details blocks must NOT appear in the prompt
        assert "calculation_details" not in context
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