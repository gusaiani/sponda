"""Tests for the CVM ENET per-filing parser.

The consolidated open-data archive is rebuilt roughly weekly, so a freshly
filed quarter can wait days before the archive path can see it. ENET is the
system companies actually file into, and it lists a filing within minutes of
delivery. These tests pin the two halves of that faster path: reading the
ENET search grid into filing records, and turning one downloaded filing
package into the same ``QuarterStatements`` the archive parser produces.
"""
import io
import zipfile
from datetime import date

import pytest

from quotes.cvm import CvmParseError
from quotes.cvm_enet import (
    EnetFiling,
    build_download_url,
    build_search_payload,
    extract_quarter_statements_from_package,
    latest_filings,
    parse_search_results,
)

ALLIED_CVM_CODE = "25330"
SECOND_QUARTER_END = date(2026, 6, 30)
FIRST_QUARTER_END = date(2026, 3, 31)

ROW_SEPARATOR = "&*"
FIELD_SEPARATOR = "$&"

DOWNLOAD_ICON_TEMPLATE = (
    "<i class='fi-download' title='Download' "
    "onclick=OpenDownloadDocumentos('{sequence}','{version}','{protocol}','{kind}')> </i>"
)


def _grid_row(
    *,
    code="02533-0",
    name="ALLIED TECNOLOGIA S.A.",
    category="ITR - Informações Trimestrais",
    reference="20260630",
    reference_display="30/06/2026",
    delivery="20260812",
    delivery_display="12/08/2026 17:45",
    status="Ativo",
    version="1",
    sequence="160482",
    protocol="025330ITR300620260100160482-70",
    kind="ITR",
    with_download=True,
):
    actions = (
        DOWNLOAD_ICON_TEMPLATE.format(
            sequence=sequence, version=version, protocol=protocol, kind=kind,
        )
        if with_download
        else "   "
    )
    return FIELD_SEPARATOR.join([
        code,
        name,
        category,
        " - ",
        "<spanOrder></spanOrder> - ",
        f"<spanOrder>{reference}</spanOrder> {reference_display}",
        f"<spanOrder>{delivery}</spanOrder> {delivery_display}",
        status,
        version,
        "AP",
        actions,
        "",
    ])


def _grid(*rows):
    return ROW_SEPARATOR.join(rows)


# --- The filing package -----------------------------------------------------


def _conta(code, description, **columns):
    column_tags = "".join(
        f"<{tag}>{value}</{tag}>" for tag, value in columns.items()
    )
    description_tag = (
        f"<DescricaoConta>{description}</DescricaoConta>" if description else
        "<DescricaoConta />"
    )
    return (
        f"<Conta><ContaFixa>True</ContaFixa><CodigoConta>{code}</CodigoConta>"
        f"{description_tag}{column_tags}</Conta>"
    )


def _income(code, description, quarter, year_to_date):
    return _conta(
        code, description,
        TrimestreAtual=quarter, AcumuladoExercicioAtual=year_to_date,
        TrimestreAnterior="0", AcumuladoExercicioAnterior="0",
    )


def _cash_flow(code, description, year_to_date):
    return _conta(
        code, description,
        Metodo="Indireto",
        AcumuladoAtualExercicio=year_to_date, AcumuladoExercicioAnterior="0",
    )


def _balance(code, description, amount):
    return _conta(
        code, description, TrimestreAtual=amount, ExercicioAnterior="0",
    )


def _statements_xml(
    *,
    cvm_code="025330",
    version="1",
    reference="30/06/2026",
    quarter_start="01/04/2026",
    fiscal_year_start="01/01/2026",
    scale="2",
    income=(),
    cash_flow=(),
    assets=(),
    liabilities=(),
    consolidated=True,
):
    statements = (
        f"<BalancoPatrimonialAtivo>{''.join(assets)}</BalancoPatrimonialAtivo>"
        f"<BalancoPatrimonialPassivo>{''.join(liabilities)}</BalancoPatrimonialPassivo>"
        f"<DemonstracaoResultado>{''.join(income)}</DemonstracaoResultado>"
        f"<DemonstracaoFluxoCaixa>{''.join(cash_flow)}</DemonstracaoFluxoCaixa>"
    )
    section = (
        f"<DfConsolidadas>{statements}</DfConsolidadas>" if consolidated
        else f"<DfIndividuais>{statements}</DfIndividuais>"
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<XmlInformacoesTrimestraisFinanceiras>"
        f"<DadosEmpresa><CodigoCvm>{cvm_code}</CodigoCvm></DadosEmpresa>"
        f"<Documento><VersaoDocumento>{version}</VersaoDocumento></Documento>"
        "<DadosITR>"
        f"<DataReferencia>{reference}</DataReferencia>"
        f"<DtInicioTrimestreAtual>{quarter_start}</DtInicioTrimestreAtual>"
        f"<DtFimTrimestreAtual>{reference}</DtFimTrimestreAtual>"
        f"<DtInicioExercicioSocialCurso>{fiscal_year_start}</DtInicioExercicioSocialCurso>"
        f"<EscalaMoeda>{scale}</EscalaMoeda>"
        f"<Formulario>{section}</Formulario>"
        "</DadosITR>"
        "</XmlInformacoesTrimestraisFinanceiras>"
    )


DECOY_METADATA_XML = '<?xml version="1.0"?><Documento><Documentos /></Documento>'


def build_package(**overrides):
    """Assemble an in-memory ENET filing zip, decoy metadata file included."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("FormularioCadastral.xml", DECOY_METADATA_XML)
        package.writestr(
            "025330ITR30-06-2026v1.xml", _statements_xml(**overrides),
        )
    return buffer.getvalue()


def _balanced_liabilities(
    *,
    total="3.547.811",
    current="1.577.752",
    noncurrent="395.873",
    equity="1.574.186",
):
    return (
        _balance("2", "Passivo Total", total),
        _balance("2.01", "Passivo Circulante", current),
        _balance("2.01.04", "Empréstimos e Financiamentos", "300.000"),
        _balance("2.01.04.03", "Financiamento por Arrendamento", "50.000"),
        _balance("2.02", "Passivo Não Circulante", noncurrent),
        _balance("2.02.01", "Empréstimos e Financiamentos", "200.000"),
        _balance("2.02.01.03", "Financiamento por Arrendamento", "80.000"),
        _balance("2.03", "Patrimônio Líquido Consolidado", equity),
    )


def _balanced_assets(*, total="3.547.811", current="2.430.222"):
    return (
        _balance("1", "Ativo Total", total),
        _balance("1.01", "Ativo Circulante", current),
    )


def build_second_quarter_package(**overrides):
    defaults = dict(
        income=(
            _income(
                "3.01", "Receita de Venda de Bens e/ou Serviços",
                "1.458.278", "2.617.716",
            ),
            _income(
                "3.11", "Lucro/Prejuízo Consolidado do Período",
                "36.594", "61.281",
            ),
        ),
        cash_flow=(
            _cash_flow("6.01", "Caixa Líquido Atividades Operacionais", "198.535"),
            _cash_flow("6.02", "Caixa Líquido Atividades de Investimento", "-3.848"),
            _cash_flow("6.03.05", "Dividendos Pagos", "-10.000"),
        ),
        assets=_balanced_assets(),
        liabilities=_balanced_liabilities(),
    )
    defaults.update(overrides)
    return build_package(**defaults)


def build_first_quarter_package(**overrides):
    defaults = dict(
        reference="31/03/2026",
        quarter_start="01/01/2026",
        cash_flow=(
            _cash_flow("6.01", "Caixa Líquido Atividades Operacionais", "69.229"),
            _cash_flow("6.02", "Caixa Líquido Atividades de Investimento", "-1.000"),
            _cash_flow("6.03.05", "Dividendos Pagos", "-4.000"),
        ),
        assets=_balanced_assets(),
        liabilities=_balanced_liabilities(),
    )
    defaults.update(overrides)
    return build_package(**defaults)


# --- Search grid ------------------------------------------------------------


def test_parses_a_filing_row_into_all_its_fields():
    filings = parse_search_results(_grid(_grid_row()))

    assert filings == [
        EnetFiling(
            cvm_code="25330",
            company_name="ALLIED TECNOLOGIA S.A.",
            reference_date=date(2026, 6, 30),
            filed_at=date(2026, 8, 12),
            version=1,
            document_number="160482",
            protocol="025330ITR300620260100160482-70",
        )
    ]


def test_normalizes_the_cvm_code_by_dropping_punctuation_and_zeros():
    filings = parse_search_results(_grid(_grid_row(code="00398-0")))
    assert filings[0].cvm_code == "3980"


def test_skips_rows_that_are_not_active():
    grid = _grid(_grid_row(status="Inativo"), _grid_row())
    assert len(parse_search_results(grid)) == 1


def test_skips_rows_without_a_download_link():
    grid = _grid(_grid_row(with_download=False), _grid_row())
    assert len(parse_search_results(grid)) == 1


def test_skips_rows_whose_download_is_not_an_itr_document():
    grid = _grid(_grid_row(kind="IPE"), _grid_row())
    assert len(parse_search_results(grid)) == 1


def test_an_empty_grid_yields_no_filings():
    assert parse_search_results("") == []


def test_latest_filings_keeps_the_highest_version_per_company_and_quarter():
    original = parse_search_results(_grid(_grid_row()))[0]
    restatement = parse_search_results(
        _grid(_grid_row(version="2", delivery="20260901",
                        delivery_display="01/09/2026 09:00"))
    )[0]

    kept = latest_filings([original, restatement])

    assert kept == [restatement]


def test_the_download_url_carries_the_document_coordinates():
    filing = parse_search_results(_grid(_grid_row()))[0]
    url = build_download_url(filing)

    assert "numSequencia=160482" in url
    assert "numVersao=1" in url
    assert "numProtocolo=025330ITR300620260100160482-70" in url
    assert "descTipo=ITR" in url


def test_the_search_payload_covers_the_window_in_enet_date_format():
    payload = build_search_payload(date(2026, 8, 1), date(2026, 8, 13))

    assert payload["dataDe"] == "01/08/2026"
    assert payload["dataAte"] == "13/08/2026"
    assert payload["categoria"] == "EST_3"


# --- The filing package -----------------------------------------------------


def test_reads_the_quarter_income_from_the_standalone_quarter_column():
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 1_458_278_000
    assert statements.net_income == 36_594_000


def test_reads_the_balance_sheet_snapshot_with_label_guards():
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.total_debt == 500_000_000
    assert statements.total_lease == 130_000_000
    assert statements.stockholders_equity == 1_574_186_000
    assert statements.total_liabilities == 3_547_811_000 - 1_574_186_000
    assert statements.current_assets == 2_430_222_000
    assert statements.current_liabilities == 1_577_752_000


def test_a_wrongly_labelled_account_is_refused_not_misread():
    liabilities = _balanced_liabilities() + (
        _balance("2.01.04", "Depósitos", "999.999"),
    )
    # The later row overwrites the borrowings account with a bank's deposits
    # label; the guard must then refuse the whole borrowings total.
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(liabilities=liabilities),
        ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.total_debt == 200_000_000


def test_first_quarter_cash_flow_reads_year_to_date_directly():
    statements = extract_quarter_statements_from_package(
        build_first_quarter_package(), ALLIED_CVM_CODE, FIRST_QUARTER_END,
    )

    assert statements.operating_cash_flow == 69_229_000
    assert statements.investment_cash_flow == -1_000_000
    assert statements.dividends_paid == -4_000_000


def test_second_quarter_cash_flow_is_differenced_against_the_previous_filing():
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
        previous_package_bytes=build_first_quarter_package(),
    )

    assert statements.operating_cash_flow == 198_535_000 - 69_229_000
    assert statements.investment_cash_flow == -3_848_000 - (-1_000_000)
    assert statements.dividends_paid == -10_000_000 - (-4_000_000)


def test_second_quarter_cash_flow_without_the_previous_filing_is_none():
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.operating_cash_flow is None
    assert statements.investment_cash_flow is None
    assert statements.dividends_paid is None
    assert statements.revenue == 1_458_278_000


def test_negative_dotted_amounts_parse_into_negative_thousands():
    statements = extract_quarter_statements_from_package(
        build_first_quarter_package(), ALLIED_CVM_CODE, FIRST_QUARTER_END,
    )

    assert statements.investment_cash_flow == -1_000_000


def test_amounts_without_thousands_separators_parse_too():
    """Americanas, Moura Dubeux and T4F file plain undotted integers."""
    income = (
        _income("3.01", "Receita de Venda de Bens e/ou Serviços",
                "16167000", "2.617.716"),
        _income("3.11", "Lucro/Prejuízo Consolidado do Período",
                "-731125", "61.281"),
    )
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(income=income),
        ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 16_167_000_000
    assert statements.net_income == -731_125_000


def test_per_share_amounts_with_comma_decimals_are_tolerated():
    income = (
        _income("3.01", "Receita de Venda de Bens e/ou Serviços",
                "1.458.278", "2.617.716"),
        _income("3.99.01.01", "ON", "0,3821", "0,6412"),
    )
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(income=income),
        ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.revenue == 1_458_278_000


def test_an_unknown_currency_scale_is_refused():
    with pytest.raises(CvmParseError, match="scale"):
        extract_quarter_statements_from_package(
            build_second_quarter_package(scale="9"),
            ALLIED_CVM_CODE, SECOND_QUARTER_END,
        )


def test_a_malformed_amount_is_refused():
    income = (_income("3.01", "Receita de Venda de Bens e/ou Serviços",
                      "1.458.27B", "2.617.716"),)
    with pytest.raises(CvmParseError, match="amount"):
        extract_quarter_statements_from_package(
            build_second_quarter_package(income=income),
            ALLIED_CVM_CODE, SECOND_QUARTER_END,
        )


def test_a_package_for_another_quarter_is_refused():
    with pytest.raises(CvmParseError, match="2026-06-30"):
        extract_quarter_statements_from_package(
            build_first_quarter_package(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
        )


def test_a_package_for_another_company_is_refused():
    with pytest.raises(CvmParseError, match="25330"):
        extract_quarter_statements_from_package(
            build_second_quarter_package(cvm_code="003980"),
            ALLIED_CVM_CODE, SECOND_QUARTER_END,
        )


def test_a_package_without_the_statements_document_is_refused():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("FormularioCadastral.xml", DECOY_METADATA_XML)

    with pytest.raises(CvmParseError, match="statements"):
        extract_quarter_statements_from_package(
            buffer.getvalue(), ALLIED_CVM_CODE, SECOND_QUARTER_END,
        )


def test_a_fourth_quarter_reference_is_refused():
    with pytest.raises(CvmParseError, match="fourth quarter|DFP"):
        extract_quarter_statements_from_package(
            build_second_quarter_package(reference="31/12/2026"),
            ALLIED_CVM_CODE, date(2026, 12, 31),
        )


def test_a_filing_with_only_individual_statements_yields_an_empty_quarter():
    statements = extract_quarter_statements_from_package(
        build_second_quarter_package(consolidated=False),
        ALLIED_CVM_CODE, SECOND_QUARTER_END,
    )

    assert statements.is_empty
