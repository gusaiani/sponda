"""Tests for reading the annual DFP, which is where the fourth quarter lives.

ITR covers Q1 to Q3 only. Q4 is never filed as a standalone period by anyone:
the DFP carries the full year and nothing else, so the quarter has to be
derived as the year minus the nine months already reported.

That derivation is the whole risk. The year is audited and the quarters are
not, so any adjustment the auditors made lands entirely in Q4 · which is
correct in the sense that the four quarters then sum to the audited year, and
wrong in the sense that Q4 absorbs corrections that belong elsewhere. The
alternative is rewriting Q1 to Q3, which would displace BRAPI's series.
"""
import io
import zipfile
from datetime import date

import pytest

from quotes.cvm import (
    CvmParseError,
    build_dfp_archive_url,
    extract_annual_statements,
)
from tests.test_cvm import BALANCE_SHEET_COLUMNS, FLOW_COLUMNS, GERDAU_CVM_CODE, _csv_bytes

YEAR = 2025
YEAR_START, YEAR_END = "2025-01-01", "2025-12-31"


def _row(columns, **overrides):
    base = {
        "CNPJ_CIA": "33.611.500/0001-19", "DT_REFER": YEAR_END, "VERSAO": "1",
        "DENOM_CIA": "GERDAU S.A.", "CD_CVM": GERDAU_CVM_CODE.zfill(6),
        "GRUPO_DFP": "DF Consolidado", "MOEDA": "REAL", "ESCALA_MOEDA": "MIL",
        "ORDEM_EXERC": "ÚLTIMO", "DT_INI_EXERC": YEAR_START, "DT_FIM_EXERC": YEAR_END,
        "CD_CONTA": "", "DS_CONTA": "", "VL_CONTA": "0.0000000000",
        "ST_CONTA_FIXA": "S",
    }
    base.update(overrides)
    return {column: base.get(column, "") for column in columns}


def flow(account, description, value, **kw):
    return _row(FLOW_COLUMNS, CD_CONTA=account, DS_CONTA=description,
                VL_CONTA=f"{value}.0000000000", **kw)


def balance(account, description, value, **kw):
    return _row(BALANCE_SHEET_COLUMNS, CD_CONTA=account, DS_CONTA=description,
                VL_CONTA=f"{value}.0000000000", **kw)


def build_dfp(income=(), assets=(), liabilities=(), cash_flow=(), year=YEAR):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"dfp_cia_aberta_DRE_con_{year}.csv",
                         _csv_bytes(FLOW_COLUMNS, income))
        archive.writestr(f"dfp_cia_aberta_BPA_con_{year}.csv",
                         _csv_bytes(BALANCE_SHEET_COLUMNS, assets))
        archive.writestr(f"dfp_cia_aberta_BPP_con_{year}.csv",
                         _csv_bytes(BALANCE_SHEET_COLUMNS, liabilities))
        archive.writestr(f"dfp_cia_aberta_DFC_MI_con_{year}.csv",
                         _csv_bytes(FLOW_COLUMNS, cash_flow))
        archive.writestr(f"dfp_cia_aberta_DFC_MD_con_{year}.csv",
                         _csv_bytes(FLOW_COLUMNS, []))
    return buffer.getvalue()


def gerdau_annual():
    return build_dfp(
        income=[
            flow("3.01", "Receita de Venda de Bens e/ou Serviços", 70_000_000),
            flow("3.11", "Lucro/Prejuízo Consolidado do Período", 5_600_000),
        ],
        assets=[
            balance("1", "Ativo Total", 81_810_298),
            balance("1.01", "Ativo Circulante", 28_573_526),
        ],
        liabilities=[
            balance("2", "Passivo Total", 81_810_298),
            balance("2.01", "Passivo Circulante", 10_360_391),
            balance("2.02", "Passivo Não Circulante", 17_715_159),
            balance("2.03", "Patrimônio Líquido Consolidado", 53_734_748),
        ],
        cash_flow=[
            flow("6.01", "Caixa Líquido Atividades Operacionais", 9_000_000),
            flow("6.02", "Caixa Líquido Atividades de Investimento", -4_000_000),
        ],
    )


# --- URL --------------------------------------------------------------------

def test_archive_url_follows_cvm_naming():
    assert build_dfp_archive_url(2025).endswith("DFP/DADOS/dfp_cia_aberta_2025.zip")


# --- Reading the year -------------------------------------------------------

def test_reads_the_full_year_flows():
    annual = extract_annual_statements(gerdau_annual(), GERDAU_CVM_CODE, YEAR)

    assert annual.quarter_end == date(2025, 12, 31)
    assert annual.revenue == 70_000_000_000
    assert annual.net_income == 5_600_000_000
    assert annual.operating_cash_flow == 9_000_000_000
    assert annual.investment_cash_flow == -4_000_000_000


def test_reads_the_year_end_balance_sheet_without_arithmetic():
    """The 31 December snapshot is filed directly; only flows are derived."""
    annual = extract_annual_statements(gerdau_annual(), GERDAU_CVM_CODE, YEAR)

    assert annual.stockholders_equity == 53_734_748_000
    assert annual.current_assets == 28_573_526_000
    assert annual.total_liabilities == (81_810_298 - 53_734_748) * 1000


def test_the_same_label_guard_applies_to_the_annual():
    """A bank's 2.03 is Provisões here exactly as it is in the ITR."""
    archive = build_dfp(
        income=[flow("3.11", "Lucro/Prejuízo Consolidado do Período", 1)],
        assets=[balance("1", "Ativo Total", 100)],
        liabilities=[
            balance("2", "Passivo Total", 100),
            balance("2.03", "Provisões", 30),
            balance("2.07", "Patrimônio Líquido Consolidado", 80),
        ],
    )
    annual = extract_annual_statements(archive, GERDAU_CVM_CODE, YEAR)

    assert annual.stockholders_equity == 80_000


def test_a_balance_sheet_that_does_not_balance_is_refused():
    archive = build_dfp(
        income=[flow("3.11", "Lucro/Prejuízo Consolidado do Período", 1)],
        assets=[balance("1", "Ativo Total", 999)],
        liabilities=[
            balance("2", "Passivo Total", 100),
            balance("2.03", "Patrimônio Líquido Consolidado", 80),
        ],
    )
    with pytest.raises(CvmParseError, match="balance"):
        extract_annual_statements(archive, GERDAU_CVM_CODE, YEAR)


def test_a_company_absent_from_the_archive_reads_as_empty():
    annual = extract_annual_statements(gerdau_annual(), "99999", YEAR)

    assert annual.is_empty


def test_a_partial_year_window_is_not_mistaken_for_the_year():
    """Filers with non-calendar fiscal years publish trailing-12-month windows
    against the same document; only the calendar year is the annual."""
    archive = build_dfp(income=[
        flow("3.11", "Lucro/Prejuízo Consolidado do Período", 999,
             DT_INI_EXERC="2024-04-01", DT_FIM_EXERC="2025-03-31"),
    ])
    annual = extract_annual_statements(archive, GERDAU_CVM_CODE, YEAR)

    assert annual.net_income is None
