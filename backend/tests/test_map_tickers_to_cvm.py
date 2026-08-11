"""Tests for the command that writes the ticker to CVM-code bridge.

Storing the mapping in the database rather than a Python dict is deliberate:
CVM's published data is dirty in places, so a wrong mapping has to be
correctable without a deploy, and a hand-set correction must survive the next
automated run.
"""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quotes.cvm_ticker_map import (
    MATCH_MANUAL,
    MATCH_NAME,
    MATCH_ROOT,
    MATCH_TICKER,
    CompanyRecord,
    SecurityListing,
)
from quotes.models import Ticker

COMMAND = "map_tickers_to_cvm"
MODULE = "quotes.management.commands.map_tickers_to_cvm"

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


def make_ticker(symbol, name="", market_cap=1_000_000, ticker_type="stock"):
    return Ticker.objects.create(
        symbol=symbol, name=name, type=ticker_type, market_cap=market_cap,
    )


def run(listings=(), companies=(), **options):
    output = StringIO()
    with patch(f"{MODULE}.load_security_listings", return_value=list(listings)), \
         patch(f"{MODULE}.download_company_registry", return_value=b""), \
         patch(f"{MODULE}.parse_company_registry", return_value=list(companies)):
        call_command(COMMAND, stdout=output, **options)
    return output.getvalue()


def listing(ticker, company):
    return SecurityListing(
        ticker=ticker, cnpj=company.cnpj, company_name=company.social_name,
    )


# --- Writing the mapping ----------------------------------------------------

@pytest.mark.django_db
def test_writes_the_code_cnpj_and_method():
    make_ticker("GGBR4", name="GERDAU S.A.")

    run([listing("GGBR4", GERDAU)], [GERDAU])

    ticker = Ticker.objects.get(symbol="GGBR4")
    assert ticker.cvm_code == "3980"
    assert ticker.cnpj == "33.611.500/0001-19"
    assert ticker.cvm_match_method == MATCH_TICKER


@pytest.mark.django_db
def test_records_the_weaker_method_that_actually_resolved_it():
    """Provenance is the point: a disputed figure is traced back through this."""
    make_ticker("KLBN3", name="KLABIN S.A.")

    run([listing("KLBN11", KLABIN)], [KLABIN])

    assert Ticker.objects.get(symbol="KLBN3").cvm_match_method == MATCH_ROOT


@pytest.mark.django_db
def test_falls_back_to_the_stored_company_name():
    make_ticker("BPAC3", name="BCO BTG PACTUAL S.A.")

    run([], [BTG])

    ticker = Ticker.objects.get(symbol="BPAC3")
    assert ticker.cvm_code == "22616"
    assert ticker.cvm_match_method == MATCH_NAME


@pytest.mark.django_db
def test_leaves_an_unresolvable_ticker_alone():
    make_ticker("ZZZZ9", name="")

    run([listing("GGBR4", GERDAU)], [GERDAU])

    ticker = Ticker.objects.get(symbol="ZZZZ9")
    assert ticker.cvm_code is None
    assert ticker.cvm_match_method == ""


# --- Scope ------------------------------------------------------------------

@pytest.mark.django_db
def test_ignores_tickers_that_are_not_brazilian():
    """CVM covers Brazil; the other ~18,000 tickers are on FMP."""
    make_ticker("AAPL", name="Apple Inc.")

    run([], [GERDAU])

    assert Ticker.objects.get(symbol="AAPL").cvm_code is None


# --- Not clobbering corrections ---------------------------------------------

@pytest.mark.django_db
def test_a_hand_set_mapping_survives_the_next_run():
    """Three tickers cannot be resolved from published data at all; those get
    set by hand, and an automated pass must not undo that."""
    make_ticker("MBRF3", name="")
    Ticker.objects.filter(symbol="MBRF3").update(
        cvm_code="26654", cvm_match_method=MATCH_MANUAL,
    )

    run([listing("MBRF3", GERDAU)], [GERDAU])

    ticker = Ticker.objects.get(symbol="MBRF3")
    assert ticker.cvm_code == "26654"
    assert ticker.cvm_match_method == MATCH_MANUAL


@pytest.mark.django_db
def test_an_automated_mapping_is_refreshed():
    make_ticker("GGBR4", name="GERDAU S.A.")
    Ticker.objects.filter(symbol="GGBR4").update(
        cvm_code="9999", cvm_match_method=MATCH_NAME,
    )

    run([listing("GGBR4", GERDAU)], [GERDAU])

    assert Ticker.objects.get(symbol="GGBR4").cvm_code == "3980"


# --- Dry run ----------------------------------------------------------------

@pytest.mark.django_db
def test_dry_run_reports_without_writing():
    make_ticker("GGBR4", name="GERDAU S.A.")

    output = run([listing("GGBR4", GERDAU)], [GERDAU], dry_run=True)

    assert Ticker.objects.get(symbol="GGBR4").cvm_code is None
    assert "GGBR4" in output or "1" in output


# --- Reporting --------------------------------------------------------------

@pytest.mark.django_db
def test_reports_a_breakdown_by_method():
    make_ticker("GGBR4", name="GERDAU S.A.")
    make_ticker("KLBN3", name="KLABIN S.A.")
    make_ticker("BPAC3", name="BCO BTG PACTUAL S.A.")

    output = run(
        [listing("GGBR4", GERDAU), listing("KLBN11", KLABIN)],
        [GERDAU, KLABIN, BTG],
    )

    assert MATCH_TICKER in output
    assert MATCH_ROOT in output
    assert MATCH_NAME in output


@pytest.mark.django_db
def test_names_the_unmapped_tickers_so_new_listings_surface():
    """The monthly run is how an IPO gets noticed rather than silently missed."""
    make_ticker("WDCN3", name="", market_cap=150_403_662)

    output = run([], [GERDAU])

    assert "WDCN3" in output


@pytest.mark.django_db
def test_a_ticker_with_no_market_cap_is_counted_but_not_flagged():
    """BDRs match the B3 shape and will never have a CVM code.

    XPBR31, PRXB31 and a dozen others are receipts over foreign issuers, which
    CVM does not register. They can never be mapped, so listing them every
    month would bury the one new listing that actually needs attention.
    """
    make_ticker("XPBR31", name="XP INC.", market_cap=None)

    output = run([], [GERDAU])

    assert "XPBR31" not in output
    assert "1 without a market cap" in output


@pytest.mark.django_db
def test_unmapped_tickers_are_ordered_by_how_much_they_matter():
    """A R$200bn bank missing is not the same as a R$10m shell missing."""
    make_ticker("TINY3", name="", market_cap=1_000)
    make_ticker("BIGG3", name="", market_cap=200_000_000_000)

    output = run([], [GERDAU])

    assert output.index("BIGG3") < output.index("TINY3")


# --- Recording a correction by hand -----------------------------------------

def run_set(*assignments, companies=(GERDAU,)):
    output = StringIO()
    with patch(f"{MODULE}.download_company_registry", return_value=b""), \
         patch(f"{MODULE}.parse_company_registry", return_value=list(companies)):
        call_command(COMMAND, *[f"--set={a}" for a in assignments], stdout=output)
    return output.getvalue()


@pytest.mark.django_db
def test_setting_a_mapping_by_hand_marks_it_manual():
    """Three tickers cannot be resolved from published data at all."""
    make_ticker("MBRF3", name="")

    run_set("MBRF3=3980")

    ticker = Ticker.objects.get(symbol="MBRF3")
    assert ticker.cvm_code == "3980"
    assert ticker.cvm_match_method == MATCH_MANUAL
    assert ticker.cnpj == "33.611.500/0001-19"


@pytest.mark.django_db
def test_setting_a_mapping_does_not_run_the_automated_pass():
    """A correction should not wait on four archive downloads."""
    make_ticker("MBRF3", name="")
    with patch(f"{MODULE}.load_security_listings") as load:
        run_set("MBRF3=3980")

    load.assert_not_called()


@pytest.mark.django_db
def test_refuses_a_code_that_no_registered_company_holds():
    """A typo here writes a wrong number onto a real company's page."""
    make_ticker("MBRF3", name="")

    with pytest.raises(CommandError, match="9999"):
        run_set("MBRF3=9999")

    assert Ticker.objects.get(symbol="MBRF3").cvm_code is None


@pytest.mark.django_db
def test_refuses_an_unknown_ticker():
    with pytest.raises(CommandError, match="NOPE3"):
        run_set("NOPE3=3980")


@pytest.mark.django_db
def test_rejects_a_malformed_assignment():
    with pytest.raises(CommandError):
        run_set("MBRF3")


@pytest.mark.django_db
def test_setting_accepts_a_lowercase_symbol():
    make_ticker("MBRF3", name="")

    run_set("mbrf3=3980")

    assert Ticker.objects.get(symbol="MBRF3").cvm_code == "3980"
