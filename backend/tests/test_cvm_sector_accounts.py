"""Tests that a CVM account number is only trusted when its label agrees.

The chart of accounts is sector-specific, and the parser originally assumed the
industrial one everywhere. For a bank the same numbers hold entirely different
quantities:

    account   industrial filer              Banco do Brasil
    1.01      Ativo Circulante              Caixa e Equivalentes de Caixa
    2.01      Passivo Circulante            Passivos Financeiros a Valor Justo
    2.02.01   Empréstimos e Financiamentos  Depósitos
    2.03      Patrimônio Líquido            Provisões

Read by number alone, a bank's customer deposits are counted as debt and its
provisions as equity — R$39bn where the real figure is R$197bn. Those are not
mislabelled fields, they are different quantities, and they feed debtToEquity,
liabilitiesToEquity and currentRatio. Every one is a plausible wrong number,
which is the kind that survives review.

Measured across the 416 consolidated filers of 2026: 404 report equity at 2.03,
7 at 2.07 and 5 at 2.08 — but all 416 carry a line labelled "Patrimônio Líquido
Consolidado". The label is the reliable key; the number is not.
"""

import pytest

from quotes.cvm import CvmParseError, extract_quarter_statements
from tests.test_cvm import (
    GERDAU_CVM_CODE,
    SECOND_QUARTER_END,
    _balance_row,
    _flow_row,
    build_archive,
)

BANK_CVM_CODE = "1023"
QUARTER_START = "2026-04-01"
YEAR_START = "2026-01-01"


def industrial_assets():
    return [
        _balance_row("1", "Ativo Total", 81_810_298),
        _balance_row("1.01", "Ativo Circulante", 28_573_526),
    ]


def industrial_liabilities():
    return [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01", "Passivo Circulante", 10_360_391),
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 909_841),
        _balance_row("2.01.04.03", "Financiamento por Arrendamento", 100_000),
        _balance_row("2.02", "Passivo Não Circulante", 17_715_159),
        _balance_row("2.02.01", "Empréstimos e Financiamentos", 12_924_566),
        _balance_row("2.02.01.03", "Financiamento por Arrendamento", 250_000),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]


def bank_assets():
    """Banco do Brasil's actual presentation."""
    return [
        _balance_row("1", "Ativo Total", 2_610_200_817, cvm_code=BANK_CVM_CODE),
        _balance_row(
            "1.01", "Caixa e Equivalentes de Caixa", 96_000_000,
            cvm_code=BANK_CVM_CODE,
        ),
        _balance_row(
            "1.02", "Ativos Financeiros", 2_400_000_000, cvm_code=BANK_CVM_CODE,
        ),
    ]


def bank_liabilities():
    return [
        _balance_row("2", "Passivo Total", 2_610_200_817, cvm_code=BANK_CVM_CODE),
        _balance_row(
            "2.01", "Passivos Financeiros Avaliados ao Valor Justo através do "
            "Resultado", 12_000_000, cvm_code=BANK_CVM_CODE,
        ),
        _balance_row(
            "2.02", "Passivos Financeiros ao Custo Amortizado", 2_300_000_000,
            cvm_code=BANK_CVM_CODE,
        ),
        _balance_row("2.02.01", "Depósitos", 900_000_000, cvm_code=BANK_CVM_CODE),
        _balance_row("2.03", "Provisões", 39_110_000, cvm_code=BANK_CVM_CODE),
        _balance_row(
            "2.07", "Patrimônio Líquido Consolidado", 196_911_536,
            cvm_code=BANK_CVM_CODE,
        ),
    ]


def quarter_flows(cvm_code=GERDAU_CVM_CODE, revenue_label="Receita de Venda de Bens e/ou Serviços"):
    return [
        _flow_row("3.01", revenue_label, 17_866_000,
                  start=QUARTER_START, end="2026-06-30", cvm_code=cvm_code),
        _flow_row("3.11", "Lucro/Prejuízo Consolidado do Período", 1_470_000,
                  start=QUARTER_START, end="2026-06-30", cvm_code=cvm_code),
    ]


def statements(*, assets, liabilities, cvm_code=GERDAU_CVM_CODE, income=None):
    archive = build_archive(
        balance_asset_rows=assets,
        balance_liability_rows=liabilities,
        income_rows=income if income is not None else quarter_flows(cvm_code),
    )
    return extract_quarter_statements(archive, cvm_code, SECOND_QUARTER_END)


# --- The industrial filer is unchanged --------------------------------------

def test_an_industrial_filer_reads_exactly_as_before():
    result = statements(assets=industrial_assets(), liabilities=industrial_liabilities())

    assert result.current_assets == 28_573_526_000
    assert result.current_liabilities == 10_360_391_000
    assert result.stockholders_equity == 53_734_748_000
    assert result.total_debt == (909_841 + 12_924_566) * 1000
    assert result.total_lease == (100_000 + 250_000) * 1000


def test_total_liabilities_is_the_balance_sheet_total_less_equity():
    """Equivalent to 2.01 + 2.02 for every one of the 404 industrial filers,
    and unlike that sum it is also defined for a bank."""
    result = statements(assets=industrial_assets(), liabilities=industrial_liabilities())

    assert result.total_liabilities == (81_810_298 - 53_734_748) * 1000
    assert result.total_liabilities == (10_360_391 + 17_715_159) * 1000


# --- The bank ---------------------------------------------------------------

def test_a_banks_equity_is_read_from_the_line_that_says_equity():
    """2.03 holds Provisões; the real figure is at 2.07."""
    result = statements(
        assets=bank_assets(), liabilities=bank_liabilities(),
        cvm_code=BANK_CVM_CODE,
        income=quarter_flows(BANK_CVM_CODE, "Receitas de Intermediação Financeira"),
    )

    assert result.stockholders_equity == 196_911_536_000
    assert result.stockholders_equity != 39_110_000_000


def test_a_banks_deposits_are_not_counted_as_debt():
    """2.02.01 is Depósitos for a bank — customer money, not borrowing."""
    result = statements(
        assets=bank_assets(), liabilities=bank_liabilities(),
        cvm_code=BANK_CVM_CODE,
        income=quarter_flows(BANK_CVM_CODE, "Receitas de Intermediação Financeira"),
    )

    assert result.total_debt is None


def test_a_bank_reports_no_current_assets_or_liabilities():
    """1.01 is cash and 2.01 is fair-valued financial liabilities. Neither is
    the current/non-current split, so currentRatio is undefined, not wrong."""
    result = statements(
        assets=bank_assets(), liabilities=bank_liabilities(),
        cvm_code=BANK_CVM_CODE,
        income=quarter_flows(BANK_CVM_CODE, "Receitas de Intermediação Financeira"),
    )

    assert result.current_assets is None
    assert result.current_liabilities is None


def test_a_banks_total_liabilities_is_still_derived():
    result = statements(
        assets=bank_assets(), liabilities=bank_liabilities(),
        cvm_code=BANK_CVM_CODE,
        income=quarter_flows(BANK_CVM_CODE, "Receitas de Intermediação Financeira"),
    )

    assert result.total_liabilities == (2_610_200_817 - 196_911_536) * 1000


# --- Other mislabelled lines seen in the real archive -----------------------

def test_a_capitalisation_line_at_the_borrowings_account_is_not_debt():
    """Three filers publish 'Capitalização' at 2.01.04."""
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01.04", "Capitalização", 500_000),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.total_debt is None


def test_an_interbank_deposit_at_the_lease_account_is_not_a_lease():
    """2.02.01.03 is 'Depósitos Interfinanceiros' for at least one filer."""
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 909_841),
        _balance_row("2.02.01.03", "Depósitos Interfinanceiros", 400_000),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.total_lease == 0


def test_labels_match_regardless_of_accent_and_case():
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01", "PASSIVO CIRCULANTE", 10_360_391),
        _balance_row("2.03", "patrimonio liquido consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.current_liabilities == 10_360_391_000
    assert result.stockholders_equity == 53_734_748_000


# --- The validation gate ----------------------------------------------------

def test_refuses_a_balance_sheet_that_does_not_balance():
    """Assets must equal liabilities plus equity. It held for 414 of 414
    filers, so a violation means the parse is wrong, not the filing."""
    assets = [
        _balance_row("1", "Ativo Total", 99_999_999),
        _balance_row("1.01", "Ativo Circulante", 28_573_526),
    ]
    with pytest.raises(CvmParseError, match="balance"):
        statements(assets=assets, liabilities=industrial_liabilities())


def test_a_rounding_difference_does_not_trip_the_gate():
    assets = [
        _balance_row("1", "Ativo Total", 81_810_299),
        _balance_row("1.01", "Ativo Circulante", 28_573_526),
    ]
    result = statements(assets=assets, liabilities=industrial_liabilities())

    assert result.stockholders_equity == 53_734_748_000


def test_a_filing_without_the_totals_is_not_gated_on_them():
    """Older filings omit the root lines; absence is not a contradiction."""
    assets = [_balance_row("1.01", "Ativo Circulante", 28_573_526)]
    liabilities = [
        _balance_row("2.01", "Passivo Circulante", 10_360_391),
        _balance_row("2.02", "Passivo Não Circulante", 17_715_159),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=assets, liabilities=liabilities)

    assert result.total_liabilities == (10_360_391 + 17_715_159) * 1000
    assert result.stockholders_equity == 53_734_748_000


def test_equity_is_none_when_no_line_claims_to_be_equity():
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.03", "Provisões", 39_110_000),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.stockholders_equity is None
    assert result.total_liabilities is None


def test_two_lines_claiming_to_be_equity_is_refused():
    """Ambiguity here silently halves or doubles every leverage ratio."""
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
        _balance_row("2.07", "Patrimônio Líquido Consolidado", 10_000_000),
    ]
    with pytest.raises(CvmParseError, match="equity"):
        statements(assets=industrial_assets(), liabilities=liabilities)


# --- Debt reported outside the standard accounts ----------------------------

def test_zero_debt_is_not_asserted_when_borrowings_are_reported_elsewhere():
    """Some filers publish the standard accounts as zeros from the fixed
    template and put borrowings under Outras Obrigações instead.

    Allos is the case: 2.01.04 and 2.02.01 are both 0, while
    2.02.02.02.07 "Empréstimos, financiamentos e debêntures" carries billions.
    Reporting 0 would put a debt-free balance sheet on a company carrying
    R$11.6bn, and debtToEquity would read 0.00 rather than being absent.
    """
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.01", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.02", "Outras Obrigações", 5_977_106),
        _balance_row(
            "2.02.02.02.07", "Empréstimos, financiamentos e debêntures", 5_556_680,
        ),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.total_debt is None


def test_a_genuinely_debt_free_filer_still_reports_zero():
    """Absence of borrowings anywhere is a fact worth stating."""
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.01", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.02", "Outras Obrigações", 1_000),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.total_debt == 0


def test_a_lease_line_does_not_count_as_borrowings_reported_elsewhere():
    """'Financiamento por Arrendamento' contains 'financiamento' but is a
    lease, which is tracked separately and must not suppress a real zero."""
    liabilities = [
        _balance_row("2", "Passivo Total", 81_810_298),
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.01", "Empréstimos e Financiamentos", 0),
        _balance_row("2.02.01.03", "Financiamento por Arrendamento", 250_000),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
    ]
    result = statements(assets=industrial_assets(), liabilities=liabilities)

    assert result.total_debt == 0
    assert result.total_lease == 250_000_000


def test_a_filer_with_real_debt_at_the_standard_accounts_is_unaffected():
    result = statements(assets=industrial_assets(), liabilities=industrial_liabilities())

    assert result.total_debt == (909_841 + 12_924_566) * 1000
