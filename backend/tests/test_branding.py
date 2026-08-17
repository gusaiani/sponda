"""The Poema track record, and its translations.

The performance line and the risk disclaimer are the two claims in Sponda's
email footers that a regulator would read. They exist in more than one
language, which creates the failure this file guards: someone updates the
figure in Portuguese and the English reader keeps seeing last quarter's.
"""
import pytest

from accounts.branding import (
    IBOVESPA_RETURN,
    IBOVESPA_RETURN_EN,
    POEMA_DISCLAIMER,
    POEMA_PERFORMANCE_LINE,
    POEMA_RETURN,
    POEMA_RETURN_EN,
    poema_disclaimer,
    poema_performance_line,
)


class TestFiguresAgreeAcrossLanguages:
    """Only the decimal separator may differ between the two editions."""

    @pytest.mark.parametrize(
        ("portuguese", "english"),
        [
            (POEMA_RETURN, POEMA_RETURN_EN),
            (IBOVESPA_RETURN, IBOVESPA_RETURN_EN),
        ],
    )
    def test_the_same_number_is_quoted_in_both(self, portuguese, english):
        assert portuguese.replace(",", ".") == english

    def test_both_returns_carry_the_figure(self):
        assert POEMA_RETURN_EN in poema_performance_line("en")
        assert POEMA_RETURN in poema_performance_line("pt")


class TestLanguageSelection:
    def test_portuguese_is_unchanged(self):
        assert poema_performance_line("pt") == POEMA_PERFORMANCE_LINE
        assert poema_disclaimer("pt") == POEMA_DISCLAIMER

    def test_english_is_translated(self):
        assert poema_disclaimer("en") == "Past performance does not guarantee future results."
        assert "Poema cumulative return" in poema_performance_line("en")

    @pytest.mark.parametrize("language", ["es", "fr", "de", "it", "zh", "", None])
    def test_an_untranslated_language_falls_back_to_portuguese(self, language):
        assert poema_performance_line(language) == POEMA_PERFORMANCE_LINE
        assert poema_disclaimer(language) == POEMA_DISCLAIMER
