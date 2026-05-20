from unittest.mock import patch

from assistant.context import build_company_context


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