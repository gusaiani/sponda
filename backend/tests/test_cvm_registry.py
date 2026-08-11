"""Tests for reading CVM's company registry and securities tables.

Two public datasets supply the ticker bridge: the FCA securities table, which
publishes trading codes against a CNPJ, and the company registry, which maps
CNPJ to CD_CVM. Neither is large, and both are latin-1 semicolon CSVs.
"""
import io
import zipfile
from datetime import date
from unittest.mock import Mock, patch

import pytest

from quotes.cvm_registry import (
    build_fca_archive_url,
    build_securities_filename,
    download_company_registry,
    download_fca_archive,
    load_security_listings,
    parse_company_registry,
    parse_fca_securities,
)

SECURITY_COLUMNS = (
    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;"
    "Valor_Mobiliario;Sigla_Classe_Acao_Preferencial;Classe_Acao_Preferencial;"
    "Codigo_Negociacao;Composicao_BDR_Unit;Mercado;Sigla_Entidade_Administradora;"
    "Entidade_Administradora;Data_Inicio_Negociacao;Data_Fim_Negociacao;Segmento;"
    "Data_Inicio_Listagem;Data_Fim_Listagem"
)

REGISTRY_COLUMNS = "CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;SIT;CD_CVM"


def security_row(ticker, cnpj="33.611.500/0001-19", name="GERDAU S.A.",
                 delisted="", version="1"):
    return (
        f"{cnpj};2026-01-01;{version};154534;{name};Ações Ordinárias;;;"
        f"{ticker};;Bolsa;B3;B3 S.A.;2006-05-31;{delisted};Novo Mercado;"
        f"1977-07-20;"
    )


def securities_csv(*rows):
    return "\n".join([SECURITY_COLUMNS, *rows]).encode("latin-1")


def fca_archive(payload, year=2026):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fca_cia_aberta_geral_2026.csv", b"unused")
        archive.writestr(build_securities_filename(year), payload)
    return buffer.getvalue()


def registry_csv(*rows):
    return "\n".join([REGISTRY_COLUMNS, *rows]).encode("latin-1")


# --- URLs and filenames -----------------------------------------------------

def test_archive_url_and_member_name_follow_cvm_naming():
    assert build_fca_archive_url(2026).endswith("FCA/DADOS/fca_cia_aberta_2026.zip")
    assert build_securities_filename(2026) == (
        "fca_cia_aberta_valor_mobiliario_2026.csv"
    )


# --- Securities -------------------------------------------------------------

def test_parses_a_published_trading_code():
    [listing] = parse_fca_securities(fca_archive(securities_csv(
        security_row("GGBR4"))), 2026)

    assert listing.ticker == "GGBR4"
    assert listing.cnpj == "33.611.500/0001-19"
    assert listing.company_name == "GERDAU S.A."
    assert listing.delisted_on is None


def test_parses_the_delisting_date_when_present():
    [listing] = parse_fca_securities(fca_archive(securities_csv(
        security_row("GGBR4", delisted="2024-03-15"))), 2026)

    assert listing.delisted_on == date(2024, 3, 15)


def test_decodes_latin_1_company_names():
    [listing] = parse_fca_securities(fca_archive(securities_csv(
        security_row("CMIN3", name="CSN MINERAÇÃO S.A."))), 2026)

    assert listing.company_name == "CSN MINERAÇÃO S.A."


def test_rows_without_a_trading_code_are_dropped():
    """Debentures and similar carry a blank code."""
    listings = parse_fca_securities(fca_archive(securities_csv(
        security_row("GGBR4"), security_row(""))), 2026)

    assert [listing.ticker for listing in listings] == ["GGBR4"]


def test_a_missing_securities_member_yields_nothing_rather_than_raising():
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("fca_cia_aberta_geral_2026.csv", b"x")

    assert parse_fca_securities(empty.getvalue(), 2026) == []


# --- Registry ---------------------------------------------------------------

def test_parses_a_registry_entry():
    [company] = parse_company_registry(registry_csv(
        "33.611.500/0001-19;GERDAU S.A.;GERDAU;ATIVO;003980"))

    assert company.cvm_code == "3980"
    assert company.cnpj == "33.611.500/0001-19"
    assert company.social_name == "GERDAU S.A."
    assert company.trade_name == "GERDAU"


def test_registry_entries_without_a_cvm_code_are_dropped():
    """A company with no CD_CVM cannot key any filing."""
    companies = parse_company_registry(registry_csv(
        "33.611.500/0001-19;GERDAU S.A.;GERDAU;ATIVO;003980",
        "08.773.135/0001-00;2W ECOBANK S.A.;;ATIVO;",
    ))

    assert [company.cvm_code for company in companies] == ["3980"]


# --- Downloads --------------------------------------------------------------

def test_downloading_the_archive_raises_on_a_server_error():
    response = Mock()
    response.raise_for_status.side_effect = ValueError("boom")
    with patch("quotes.cvm_registry.requests.get", return_value=response):
        with pytest.raises(ValueError):
            download_fca_archive(2026)


def test_downloading_the_registry_returns_its_bytes():
    response = Mock(content=b"CNPJ_CIA;", raise_for_status=Mock())
    with patch("quotes.cvm_registry.requests.get", return_value=response) as get:
        assert download_company_registry() == b"CNPJ_CIA;"

    assert "cad_cia_aberta.csv" in get.call_args.args[0]


# --- Loading several years --------------------------------------------------

def test_loading_several_years_prefers_the_most_recent_listing():
    """A ticker reassigned to another company must not resolve to both.

    Feeding every year in at once would make such a ticker ambiguous and drop
    it; taking the newest year that lists it keeps the current owner.
    """
    archives = {
        2025: fca_archive(securities_csv(
            security_row("GGBR4", cnpj="00.000.000/0001-00")), 2025),
        2026: fca_archive(securities_csv(security_row("GGBR4")), 2026),
    }

    with patch("quotes.cvm_registry.download_fca_archive", archives.get):
        listings = load_security_listings([2025, 2026])

    assert [(listing.ticker, listing.cnpj) for listing in listings] == [
        ("GGBR4", "33.611.500/0001-19"),
    ]


def test_loading_several_years_unions_tickers_only_older_years_carry():
    archives = {
        2025: fca_archive(securities_csv(security_row("KLBN11")), 2025),
        2026: fca_archive(securities_csv(security_row("GGBR4")), 2026),
    }

    with patch("quotes.cvm_registry.download_fca_archive", archives.get):
        listings = load_security_listings([2025, 2026])

    assert sorted(listing.ticker for listing in listings) == ["GGBR4", "KLBN11"]


def test_a_year_that_cannot_be_fetched_does_not_lose_the_others():
    """Early years 404 as CVM's coverage thins; that must not be fatal."""
    def fetch(year):
        if year == 2024:
            raise OSError("404")
        return fca_archive(securities_csv(security_row("GGBR4")), year)

    with patch("quotes.cvm_registry.download_fca_archive", fetch):
        listings = load_security_listings([2024, 2026])

    assert [listing.ticker for listing in listings] == ["GGBR4"]
