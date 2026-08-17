"""Centralized branding constants. Update here to update everywhere:
site footer, welcome email, and any future templates.

Portuguese is the original and stays the fallback for every language. English
exists alongside it because the MCP announcement goes to a list that is
roughly half English-speaking, and a risk disclaimer nobody can read is not a
disclaimer. Keep the two editions quoting the same figures: the tests in
test_branding.py compare them digit by digit.
"""

DEFAULT_BRANDING_LANGUAGE = "pt"

POEMA_RETURN = "339,17%"
IBOVESPA_RETURN = "185,64%"
POEMA_PERIOD = "jan/2017–jun/2026"

# The same figures with English number formatting and month names.
POEMA_RETURN_EN = "339.17%"
IBOVESPA_RETURN_EN = "185.64%"
POEMA_PERIOD_EN = "Jan 2017 to Jun 2026"

POEMA_PERFORMANCE_LINE = (
    f"Retorno acumulado da Poema: {POEMA_RETURN} vs Ibovespa: {IBOVESPA_RETURN} ({POEMA_PERIOD})."
)
POEMA_DISCLAIMER = "Resultados passados não garantem resultados futuros."
POEMA_CTA = "Procuramos parceiros com visão de longo prazo."

POEMA_PERFORMANCE_LINE_EN = (
    f"Poema cumulative return: {POEMA_RETURN_EN} vs Ibovespa: "
    f"{IBOVESPA_RETURN_EN} ({POEMA_PERIOD_EN})."
)
POEMA_DISCLAIMER_EN = "Past performance does not guarantee future results."

PERFORMANCE_LINE_BY_LANGUAGE = {
    "pt": POEMA_PERFORMANCE_LINE,
    "en": POEMA_PERFORMANCE_LINE_EN,
}
DISCLAIMER_BY_LANGUAGE = {
    "pt": POEMA_DISCLAIMER,
    "en": POEMA_DISCLAIMER_EN,
}


def poema_performance_line(language):
    """Return the track-record line, falling back to Portuguese."""
    return _translated(PERFORMANCE_LINE_BY_LANGUAGE, language)


def poema_disclaimer(language):
    """Return the risk disclaimer, falling back to Portuguese."""
    return _translated(DISCLAIMER_BY_LANGUAGE, language)


def _translated(translations, language):
    return translations.get(language) or translations[DEFAULT_BRANDING_LANGUAGE]
