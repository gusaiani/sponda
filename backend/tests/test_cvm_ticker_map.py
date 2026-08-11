"""Tests for resolving a B3 ticker to the CVM code that keys its filings.

CVM keys everything by CD_CVM and CNPJ, never by ticker, so nothing can be
ingested from CVM until this bridge exists. Three sources of evidence are used,
strongest first:

1. The FCA securities table publishes ``Codigo_Negociacao`` — the ticker —
   against a CNPJ. Authoritative when present and well-formed.
2. The four-letter ticker root. B3 gives one company one root (KLBN3, KLBN4,
   KLBN11), and the FCA sometimes lists only the unit.
3. The company name against the CVM registry, normalised for the rendering
   differences between the two datasets.

The field is dirty in ways that matter: 61 of the published Codigo_Negociacao
values are not tickers at all ("0", "1545-8", and for CSN the CVM code "4030"
sitting in the ticker column). An unvalidated read of that field maps tickers
to the wrong company, which is worse than not mapping them.
"""
from datetime import date

import pytest

from quotes.cvm_ticker_map import (
    MATCH_NAME,
    MATCH_ROOT,
    MATCH_TICKER,
    CompanyRecord,
    SecurityListing,
    TickerResolver,
    normalize_company_name,
)

GERDAU = CompanyRecord(
    cvm_code="3980", cnpj="33.611.500/0001-19",
    social_name="GERDAU S.A.", trade_name="GERDAU",
)
KLABIN = CompanyRecord(
    cvm_code="12653", cnpj="89.637.490/0001-45",
    social_name="KLABIN S.A.", trade_name="KLABIN",
)
BTG = CompanyRecord(
    cvm_code="22616", cnpj="30.306.294/0001-45",
    social_name="BANCO BTG PACTUAL S/A", trade_name="BTG PACTUAL",
)
CSN = CompanyRecord(
    cvm_code="4030", cnpj="33.042.730/0001-04",
    social_name="COMPANHIA SIDERURGICA NACIONAL", trade_name="CSN",
)


def listing(ticker, company, delisted_on=None):
    return SecurityListing(
        ticker=ticker, cnpj=company.cnpj,
        company_name=company.social_name, delisted_on=delisted_on,
    )


def resolver(listings=(), companies=()):
    return TickerResolver(listings=list(listings), companies=list(companies))


# --- Strategy 1: the published ticker ---------------------------------------

def test_resolves_a_ticker_the_fca_publishes():
    match = resolver([listing("GGBR4", GERDAU)], [GERDAU]).resolve("GGBR4")

    assert match.cvm_code == "3980"
    assert match.cnpj == "33.611.500/0001-19"
    assert match.method == MATCH_TICKER


def test_resolution_is_case_insensitive():
    assert resolver([listing("GGBR4", GERDAU)], [GERDAU]).resolve("ggbr4").cvm_code == (
        "3980"
    )


def test_a_listing_whose_company_is_not_in_the_registry_yields_no_code():
    """Without the registry there is no CD_CVM, and a CNPJ alone is not enough."""
    assert resolver([listing("GGBR4", GERDAU)], []).resolve("GGBR4") is None


def test_a_delisted_listing_still_identifies_the_company():
    """Delisting changes whether it trades, not who filed the statements."""
    match = resolver(
        [listing("GGBR4", GERDAU, delisted_on=date(2020, 1, 1))], [GERDAU],
    ).resolve("GGBR4")

    assert match.cvm_code == "3980"


# --- Rejecting the dirty values ---------------------------------------------

@pytest.mark.parametrize("published", ["4030", "0", "00000", "1545-8", "", "1212"])
def test_ignores_published_codes_that_are_not_b3_tickers(published):
    """CSN publishes its CVM code in the ticker column; others publish zeros.

    Trusting the field blindly would attach a real ticker to whatever company
    happened to publish that string.
    """
    resolved = resolver([listing(published, CSN)], [CSN]).resolve(published)

    assert resolved is None


def test_a_malformed_code_does_not_block_a_later_correct_source():
    """CSN is exactly this case: junk in the FCA, recoverable by name."""
    match = resolver([listing("4030", CSN)], [CSN]).resolve(
        "CSNA3", company_name="CIA SIDERURGICA NACIONAL",
    )

    assert match.cvm_code == "4030"
    assert match.method == MATCH_NAME


# --- Strategy 2: the ticker root --------------------------------------------

def test_resolves_a_share_when_only_the_unit_is_published():
    """Klabin publishes KLBN11; Sponda tracks KLBN3 and KLBN4."""
    resolve = resolver([listing("KLBN11", KLABIN)], [KLABIN]).resolve

    for symbol in ("KLBN3", "KLBN4"):
        match = resolve(symbol)
        assert match.cvm_code == "12653"
        assert match.method == MATCH_ROOT


def test_the_root_is_not_used_when_it_spans_two_companies():
    """A shared root is not evidence, and a wrong code is worse than none."""
    other = CompanyRecord(
        cvm_code="99999", cnpj="00.000.000/0001-00",
        social_name="KLABIN IRMAOS S.A.", trade_name="",
    )
    resolved = resolver(
        [listing("KLBN11", KLABIN), listing("KLBN5", other)], [KLABIN, other],
    ).resolve("KLBN3")

    assert resolved is None


def test_an_exact_ticker_beats_its_own_root():
    sibling = CompanyRecord(
        cvm_code="55555", cnpj="11.111.111/0001-11",
        social_name="OUTRA S.A.", trade_name="",
    )
    match = resolver(
        [listing("GGBR4", GERDAU), listing("GGBR11", sibling)],
        [GERDAU, sibling],
    ).resolve("GGBR4")

    assert match.cvm_code == "3980"
    assert match.method == MATCH_TICKER


# --- Strategy 3: the company name -------------------------------------------

def test_resolves_by_name_when_the_ticker_is_absent_entirely():
    match = resolver([], [BTG]).resolve("BPAC3", company_name="BCO BTG PACTUAL S.A.")

    assert match.cvm_code == "22616"
    assert match.method == MATCH_NAME


def test_name_matching_needs_a_name():
    assert resolver([], [BTG]).resolve("BPAC3") is None


def test_an_ambiguous_name_resolves_to_nothing():
    twin = CompanyRecord(
        cvm_code="77777", cnpj="22.222.222/0001-22",
        social_name="GERDAU S.A.", trade_name="",
    )
    assert resolver([], [GERDAU, twin]).resolve(
        "GGBR4", company_name="GERDAU S.A.",
    ) is None


def test_matches_against_the_trade_name_too():
    match = resolver([], [CSN]).resolve("CSNA3", company_name="CSN")

    assert match.cvm_code == "4030"


# --- Name normalisation -----------------------------------------------------

@pytest.mark.parametrize("left,right", [
    ("BCO BTG PACTUAL S.A.", "BANCO BTG PACTUAL S/A"),
    ("CIA SIDERURGICA NACIONAL", "COMPANHIA SIDERÚRGICA NACIONAL"),
    ("ALPARGATAS S.A.", "ALPARGATAS SA"),
    ("AMERICANAS S.A", "AMERICANAS S.A. - EM RECUPERAÇÃO JUDICIAL"),
    ("CSN MINERAÇÃO S.A.", "CSN MINERACAO SA"),
    ("  Gerdau   S.A.  ", "GERDAU S.A."),
])
def test_the_two_datasets_render_the_same_company_the_same_way(left, right):
    assert normalize_company_name(left) == normalize_company_name(right)


@pytest.mark.parametrize("left,right", [
    ("GERDAU S.A.", "METALURGICA GERDAU S.A."),
    ("KLABIN S.A.", "KLABIN IRMAOS S.A."),
])
def test_normalisation_does_not_collapse_distinct_companies(left, right):
    assert normalize_company_name(left) != normalize_company_name(right)


def test_normalising_nothing_is_empty_not_an_error():
    assert normalize_company_name(None) == ""
    assert normalize_company_name("") == ""


def test_an_empty_name_never_matches_a_company_with_an_empty_trade_name():
    """Blank trade names are common; they must not become a wildcard."""
    nameless = CompanyRecord(
        cvm_code="123", cnpj="99.999.999/0001-99", social_name="X S.A.", trade_name="",
    )
    assert resolver([], [nameless]).resolve("XXXX3", company_name="") is None


# --- Ordering ---------------------------------------------------------------

def test_strategies_are_tried_strongest_first():
    """One company reachable three ways must resolve by the published ticker."""
    resolve = resolver(
        [listing("KLBN3", KLABIN), listing("KLBN11", KLABIN)], [KLABIN],
    ).resolve

    assert resolve("KLBN3", company_name="KLABIN S.A.").method == MATCH_TICKER


def test_an_unknown_ticker_resolves_to_nothing():
    assert resolver([listing("GGBR4", GERDAU)], [GERDAU]).resolve("ZZZZ9") is None
