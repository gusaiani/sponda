"""Tests for seed_quarter_from_cvm — manual quarter seeding from CVM open data."""
from datetime import date
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings

from tests.test_cvm import build_archive, _balance_row, _flow_row


SECOND_QUARTER = "2026-06-30"
COMMAND_MODULE = "quotes.management.commands.seed_quarter_from_cvm"


def gerdau_archive():
    """A minimal but complete 2Q26 filing for Gerdau S.A. (CD_CVM 003980)."""
    return build_archive(
        income_rows=[
            _flow_row("3.01", "Receita de Venda", 17870632,
                      start="2026-04-01", end="2026-06-30"),
            _flow_row("3.11", "Lucro/Prejuízo Consolidado do Período", 1466046,
                      start="2026-04-01", end="2026-06-30"),
        ],
        indirect_cash_flow_rows=[
            _flow_row("6.01", "Caixa Líquido Atividades Operacionais", 1509307,
                      start="2026-01-01", end="2026-03-31",
                      reference_date="2026-03-31"),
            _flow_row("6.02", "Caixa Líquido Atividades de Investimento", -1200924,
                      start="2026-01-01", end="2026-03-31",
                      reference_date="2026-03-31"),
            _flow_row("6.01", "Caixa Líquido Atividades Operacionais", 3044323,
                      start="2026-01-01", end="2026-06-30"),
            _flow_row("6.02", "Caixa Líquido Atividades de Investimento", -2298239,
                      start="2026-01-01", end="2026-06-30"),
        ],
        balance_asset_rows=[
            _balance_row("1.01", "Ativo Circulante", 29000000),
        ],
        balance_liability_rows=[
            _balance_row("2.01", "Passivo Circulante", 10500000),
            _balance_row("2.01.04", "Empréstimos e Financiamentos", 900000),
            _balance_row("2.02", "Passivo Não Circulante", 17800000),
            _balance_row("2.02.01", "Empréstimos e Financiamentos", 13000000),
            _balance_row("2.03", "Patrimônio Líquido Consolidado", 53000000),
        ],
    )


@pytest.fixture
def archive_download():
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = gerdau_archive()
        yield download


@pytest.mark.django_db
def test_seeds_earnings_cash_flow_and_balance_sheet(archive_download):
    call_command("seed_quarter_from_cvm", "--quarter", SECOND_QUARTER, "--ticker", "GGBR3")

    earnings = QuarterlyEarnings.objects.get(ticker="GGBR3", end_date=date(2026, 6, 30))
    assert earnings.revenue == 17_870_632_000
    assert earnings.net_income == 1_466_046_000

    cash_flow = QuarterlyCashFlow.objects.get(ticker="GGBR3", end_date=date(2026, 6, 30))
    assert cash_flow.operating_cash_flow == 1_535_016_000
    assert cash_flow.investment_cash_flow == -1_097_315_000

    balance = BalanceSheet.objects.get(ticker="GGBR3", end_date=date(2026, 6, 30))
    assert balance.total_debt == 13_900_000_000
    assert balance.total_lease == 0
    assert balance.total_liabilities == 28_300_000_000
    assert balance.stockholders_equity == 53_000_000_000


@pytest.mark.django_db
def test_leaves_free_cash_flow_unset_so_fundamentals_derives_it(archive_download):
    """BRAPI never reports FCF; fundamentals.py falls back to OCF + investing."""
    call_command("seed_quarter_from_cvm", "--quarter", SECOND_QUARTER, "--ticker", "GGBR3")

    cash_flow = QuarterlyCashFlow.objects.get(ticker="GGBR3", end_date=date(2026, 6, 30))
    assert cash_flow.free_cash_flow is None


@pytest.mark.django_db
def test_seeds_every_requested_ticker_from_one_download(archive_download):
    call_command(
        "seed_quarter_from_cvm", "--quarter", SECOND_QUARTER,
        "--ticker", "GGBR3", "--ticker", "GGBR4",
    )

    assert QuarterlyEarnings.objects.filter(end_date=date(2026, 6, 30)).count() == 2
    assert archive_download.call_count == 1


@pytest.mark.django_db
def test_rerunning_updates_in_place_instead_of_duplicating(archive_download):
    QuarterlyEarnings.objects.create(
        ticker="GGBR3", end_date=date(2026, 6, 30), revenue=1, net_income=1,
    )

    call_command("seed_quarter_from_cvm", "--quarter", SECOND_QUARTER, "--ticker", "GGBR3")

    earnings = QuarterlyEarnings.objects.get(ticker="GGBR3", end_date=date(2026, 6, 30))
    assert earnings.revenue == 17_870_632_000
    assert QuarterlyEarnings.objects.filter(ticker="GGBR3").count() == 1


@pytest.mark.django_db
def test_dry_run_writes_nothing(archive_download):
    call_command(
        "seed_quarter_from_cvm", "--quarter", SECOND_QUARTER,
        "--ticker", "GGBR3", "--dry-run",
    )

    assert not QuarterlyEarnings.objects.exists()
    assert not QuarterlyCashFlow.objects.exists()
    assert not BalanceSheet.objects.exists()


@pytest.mark.django_db
def test_unknown_ticker_is_rejected_before_any_download():
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        with pytest.raises(CommandError, match="XXXX3"):
            call_command(
                "seed_quarter_from_cvm", "--quarter", SECOND_QUARTER, "--ticker", "XXXX3",
            )
    download.assert_not_called()


@pytest.mark.django_db
def test_skips_a_company_absent_from_the_archive():
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = build_archive()
        call_command(
            "seed_quarter_from_cvm", "--quarter", SECOND_QUARTER, "--ticker", "GGBR3",
        )

    assert not QuarterlyEarnings.objects.exists()
    assert not BalanceSheet.objects.exists()


@pytest.mark.django_db
def test_rejects_a_non_quarter_end_date(archive_download):
    with pytest.raises(CommandError, match="quarter end"):
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-05-31", "--ticker", "GGBR3",
        )


# --- The continuity gate ----------------------------------------------------

def _equity_continuity_archive(equity_thousands):
    """A Gerdau-shaped archive with equity set to a chosen value."""
    from tests.test_cvm import _balance_row, _flow_row, build_archive

    return build_archive(
        balance_asset_rows=[
            _balance_row("1", "Ativo Total", 81_810_298),
            _balance_row("1.01", "Ativo Circulante", 28_573_526),
        ],
        balance_liability_rows=[
            _balance_row("2", "Passivo Total", 81_810_298),
            _balance_row("2.01", "Passivo Circulante", 10_360_391),
            _balance_row("2.02", "Passivo Não Circulante", 17_715_159),
            _balance_row(
                "2.03", "Patrimônio Líquido Consolidado", equity_thousands,
            ),
        ],
        income_rows=[
            _flow_row("3.11", "Lucro/Prejuízo Consolidado do Período", 1_470_000,
                      start="2026-04-01", end="2026-06-30"),
        ],
    )


@pytest.mark.django_db
def test_refuses_equity_that_jumped_by_an_order_of_magnitude():
    """A tenfold move in one quarter is a parse fault, not a corporate event.

    This is the last line of defence: the numbers that get here are already
    internally consistent, so what it catches is a plausible wrong value.
    """
    BalanceSheet.objects.create(
        ticker="GGBR3", end_date=date(2026, 3, 31),
        stockholders_equity=53_000_000_000,
    )
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = _equity_continuity_archive(530_000_000)

        with pytest.raises(CommandError, match="equity"):
            call_command(
                "seed_quarter_from_cvm", "--quarter", "2026-06-30",
                "--ticker", "GGBR3",
            )

    assert not BalanceSheet.objects.filter(
        ticker="GGBR3", end_date=date(2026, 6, 30),
    ).exists()


@pytest.mark.django_db
def test_accepts_an_ordinary_quarterly_move_in_equity():
    BalanceSheet.objects.create(
        ticker="GGBR3", end_date=date(2026, 3, 31),
        stockholders_equity=53_000_000_000,
    )
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = _equity_continuity_archive(55_000_000)
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30", "--ticker", "GGBR3",
        )

    assert BalanceSheet.objects.get(
        ticker="GGBR3", end_date=date(2026, 6, 30),
    ).stockholders_equity == 55_000_000_000


@pytest.mark.django_db
def test_the_first_quarter_ever_seeded_has_nothing_to_compare_against():
    with patch(f"{COMMAND_MODULE}.download_itr_archive") as download:
        download.return_value = _equity_continuity_archive(55_000_000)
        call_command(
            "seed_quarter_from_cvm", "--quarter", "2026-06-30", "--ticker", "GGBR3",
        )

    assert BalanceSheet.objects.filter(ticker="GGBR3").count() == 1
