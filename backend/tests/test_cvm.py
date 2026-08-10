"""Tests for the CVM ITR open-data parser.

The CVM publishes quarterly filings (ITR) as open data. These tests pin the
account mapping and the period arithmetic that turn a filing into the same
shape BRAPI delivers, so a CVM-sourced quarter is drop-in compatible with a
BRAPI-sourced one.
"""
import io
import zipfile
from datetime import date

import pytest

from quotes.cvm import (
    CvmParseError,
    build_itr_archive_url,
    extract_quarter_statements,
)


BALANCE_SHEET_COLUMNS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_FIM_EXERC", "CD_CONTA",
    "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]

FLOW_COLUMNS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]

GERDAU_CVM_CODE = "3980"
FIRST_QUARTER_END = date(2026, 3, 31)
SECOND_QUARTER_END = date(2026, 6, 30)


def _balance_row(
    account, description, value, *, reference_date="2026-06-30", version="1",
    order="ÚLTIMO", scale="MIL", cvm_code=GERDAU_CVM_CODE,
):
    return {
        "CNPJ_CIA": "33.611.500/0001-19",
        "DT_REFER": reference_date,
        "VERSAO": version,
        "DENOM_CIA": "GERDAU S.A.",
        "CD_CVM": cvm_code.zfill(6),
        "GRUPO_DFP": "DF Consolidado - Balanço Patrimonial",
        "MOEDA": "REAL",
        "ESCALA_MOEDA": scale,
        "ORDEM_EXERC": order,
        "DT_FIM_EXERC": reference_date,
        "CD_CONTA": account,
        "DS_CONTA": description,
        "VL_CONTA": f"{value}.0000000000",
        "ST_CONTA_FIXA": "S",
    }


def _flow_row(
    account, description, value, *, start, end, reference_date="2026-06-30",
    version="1", order="ÚLTIMO", scale="MIL", cvm_code=GERDAU_CVM_CODE,
):
    return {
        "CNPJ_CIA": "33.611.500/0001-19",
        "DT_REFER": reference_date,
        "VERSAO": version,
        "DENOM_CIA": "GERDAU S.A.",
        "CD_CVM": cvm_code.zfill(6),
        "GRUPO_DFP": "DF Consolidado",
        "MOEDA": "REAL",
        "ESCALA_MOEDA": scale,
        "ORDEM_EXERC": order,
        "DT_INI_EXERC": start,
        "DT_FIM_EXERC": end,
        "CD_CONTA": account,
        "DS_CONTA": description,
        "VL_CONTA": f"{value}.0000000000",
        "ST_CONTA_FIXA": "S",
    }


def _csv_bytes(columns, rows):
    buffer = io.StringIO()
    buffer.write(";".join(columns) + "\n")
    for row in rows:
        buffer.write(";".join(str(row[column]) for column in columns) + "\n")
    return buffer.getvalue().encode("latin-1")


def build_archive(
    year=2026, balance_asset_rows=(), balance_liability_rows=(),
    income_rows=(), indirect_cash_flow_rows=(), direct_cash_flow_rows=(),
):
    """Assemble an in-memory ITR zip with the five statements we read."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            f"itr_cia_aberta_BPA_con_{year}.csv",
            _csv_bytes(BALANCE_SHEET_COLUMNS, balance_asset_rows),
        )
        archive.writestr(
            f"itr_cia_aberta_BPP_con_{year}.csv",
            _csv_bytes(BALANCE_SHEET_COLUMNS, balance_liability_rows),
        )
        archive.writestr(
            f"itr_cia_aberta_DRE_con_{year}.csv",
            _csv_bytes(FLOW_COLUMNS, income_rows),
        )
        archive.writestr(
            f"itr_cia_aberta_DFC_MI_con_{year}.csv",
            _csv_bytes(FLOW_COLUMNS, indirect_cash_flow_rows),
        )
        archive.writestr(
            f"itr_cia_aberta_DFC_MD_con_{year}.csv",
            _csv_bytes(FLOW_COLUMNS, direct_cash_flow_rows),
        )
    return buffer.getvalue()


# --- URL construction -------------------------------------------------------

def test_builds_the_itr_archive_url_for_a_year():
    assert build_itr_archive_url(2026) == (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/"
        "itr_cia_aberta_2026.zip"
    )


# --- Income statement -------------------------------------------------------

def test_prefers_the_native_three_month_income_column():
    """ITR income statements carry both the YTD and the standalone quarter."""
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 34586293,
                  start="2026-01-01", end="2026-06-30"),
        _flow_row("3.01", "Receita de Venda", 17870632,
                  start="2026-04-01", end="2026-06-30"),
        _flow_row("3.11", "Lucro/Prejuízo Consolidado do Período", 2479401,
                  start="2026-01-01", end="2026-06-30"),
        _flow_row("3.11", "Lucro/Prejuízo Consolidado do Período", 1466046,
                  start="2026-04-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000
    assert statements.net_income == 1_466_046_000


def test_falls_back_to_differencing_when_only_year_to_date_is_filed():
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 16715661,
                  start="2026-01-01", end="2026-03-31",
                  reference_date="2026-03-31"),
        _flow_row("3.01", "Receita de Venda", 34586293,
                  start="2026-01-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000


def test_first_quarter_reads_year_to_date_without_differencing():
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 16715661,
                  start="2026-01-01", end="2026-03-31",
                  reference_date="2026-03-31"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, FIRST_QUARTER_END,
    )

    assert statements.revenue == 16_715_661_000


def test_ignores_prior_year_comparative_rows():
    """PENÚLTIMO rows are last year's same period, not this quarter."""
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 99999999,
                  start="2025-04-01", end="2025-06-30", order="PENÚLTIMO"),
        _flow_row("3.01", "Receita de Venda", 17870632,
                  start="2026-04-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000


def test_uses_the_latest_document_version_on_restatement():
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 11111111,
                  start="2026-04-01", end="2026-06-30", version="1"),
        _flow_row("3.01", "Receita de Venda", 17870632,
                  start="2026-04-01", end="2026-06-30", version="2"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000


def test_ignores_other_companies():
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 169530000,
                  start="2026-04-01", end="2026-06-30", cvm_code="9512"),
        _flow_row("3.01", "Receita de Venda", 17870632,
                  start="2026-04-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000


def test_unit_scale_is_not_multiplied():
    archive = build_archive(income_rows=[
        _flow_row("3.01", "Receita de Venda", 17870632000,
                  start="2026-04-01", end="2026-06-30", scale="UNIDADE"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 17_870_632_000


# --- Cash flow --------------------------------------------------------------

def test_differences_year_to_date_cash_flow_into_a_single_quarter():
    """Cash flow statements are filed YTD only, so the quarter is a delta."""
    archive = build_archive(indirect_cash_flow_rows=[
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
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.operating_cash_flow == 1_535_016_000
    assert statements.investment_cash_flow == -1_097_315_000


def test_reads_the_direct_method_cash_flow_when_indirect_is_absent():
    archive = build_archive(direct_cash_flow_rows=[
        _flow_row("6.01", "Caixa Líquido Atividades Operacionais", 500000,
                  start="2026-04-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.operating_cash_flow == 500_000_000


def test_sums_dividend_lines_within_financing_activities():
    archive = build_archive(indirect_cash_flow_rows=[
        _flow_row("6.03.02", "Dividendos e juros sobre o capital próprio pagos",
                  -187041, start="2026-01-01", end="2026-03-31",
                  reference_date="2026-03-31"),
        _flow_row("6.03.02", "Dividendos e juros sobre o capital próprio pagos",
                  -651000, start="2026-01-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.dividends_paid == -463_959_000


def test_dividend_detection_skips_interest_on_borrowings_and_inflows():
    archive = build_archive(indirect_cash_flow_rows=[
        _flow_row("6.03.04", "Amortizações de juros - financiamentos", -3103000,
                  start="2026-04-01", end="2026-06-30"),
        _flow_row("6.02.05", "Dividendos recebidos", 9000,
                  start="2026-04-01", end="2026-06-30"),
        _flow_row("6.03.05", "Dividendos pagos a acionistas", -11639000,
                  start="2026-04-01", end="2026-06-30"),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.dividends_paid == -11_639_000_000


# --- Balance sheet ----------------------------------------------------------

def test_balance_sheet_totals_debt_leases_and_equity():
    archive = build_archive(
        balance_asset_rows=[
            _balance_row("1.01", "Ativo Circulante", 28573526),
        ],
        balance_liability_rows=[
            _balance_row("2.01", "Passivo Circulante", 10360391),
            _balance_row("2.01.04", "Empréstimos e Financiamentos", 909841),
            _balance_row("2.01.04.03", "Financiamento por Arrendamento", 100000),
            _balance_row("2.02", "Passivo Não Circulante", 17715159),
            _balance_row("2.02.01", "Empréstimos e Financiamentos", 12924566),
            _balance_row("2.02.01.03", "Financiamento por Arrendamento", 250000),
            _balance_row("2.03", "Patrimônio Líquido Consolidado", 52971989),
        ],
    )

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.current_assets == 28_573_526_000
    assert statements.current_liabilities == 10_360_391_000
    assert statements.total_liabilities == 28_075_550_000
    assert statements.stockholders_equity == 52_971_989_000
    assert statements.total_debt == 13_834_407_000
    assert statements.total_lease == 350_000_000


def test_balance_sheet_reads_the_quarter_end_snapshot_not_the_comparative():
    archive = build_archive(balance_liability_rows=[
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 99999999,
                     reference_date="2026-06-30", order="PENÚLTIMO"),
        _balance_row("2.03", "Patrimônio Líquido Consolidado", 52971989),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.stockholders_equity == 52_971_989_000


def test_absent_lease_accounts_report_zero_not_none():
    """Companies without leases omit the line; downstream expects 0."""
    archive = build_archive(balance_liability_rows=[
        _balance_row("2.01.04", "Empréstimos e Financiamentos", 909841),
        _balance_row("2.02.01", "Empréstimos e Financiamentos", 12924566),
    ])

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.total_lease == 0


def test_missing_accounts_are_none_rather_than_zero():
    archive = build_archive()

    statements = extract_quarter_statements(
        archive, GERDAU_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue is None
    assert statements.net_income is None
    assert statements.operating_cash_flow is None
    assert statements.stockholders_equity is None
    assert statements.is_empty


# --- Guard rails ------------------------------------------------------------

def test_rejects_a_fourth_quarter_because_itr_does_not_cover_it():
    archive = build_archive()

    with pytest.raises(CvmParseError, match="DFP"):
        extract_quarter_statements(archive, GERDAU_CVM_CODE, date(2026, 12, 31))


def test_rejects_a_date_that_is_not_a_quarter_end():
    archive = build_archive()

    with pytest.raises(CvmParseError, match="quarter end"):
        extract_quarter_statements(archive, GERDAU_CVM_CODE, date(2026, 5, 31))
