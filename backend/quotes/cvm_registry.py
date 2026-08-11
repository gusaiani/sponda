"""Read the CVM's company registry and its published securities tables.

Two small public datasets supply everything the ticker bridge needs:

* **FCA securities** (``fca_cia_aberta_valor_mobiliario_<year>.csv``, inside a
  ~350 KB annual zip) publishes ``Codigo_Negociacao`` — the B3 trading code —
  against a CNPJ.
* **The company registry** (``cad_cia_aberta.csv``, ~1.4 MB, rebuilt daily)
  maps CNPJ to ``CD_CVM``, which is what every filing is keyed by.

Both are latin-1 semicolon CSVs. Neither is big enough to warrant the ranged
reads the ITR archive needs, so they are fetched whole.

The FCA is an annual form, so a given year lists only the companies that filed
in it. Several years are read and reconciled newest-first (see
``load_security_listings``).
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import date

import requests

from .cvm_ticker_map import CompanyRecord, SecurityListing

logger = logging.getLogger(__name__)

FCA_ARCHIVE_URL_TEMPLATE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/"
    "fca_cia_aberta_{year}.zip"
)
SECURITIES_FILENAME_TEMPLATE = "fca_cia_aberta_valor_mobiliario_{year}.csv"
COMPANY_REGISTRY_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
)

DOWNLOAD_TIMEOUT_SECONDS = 120
CSV_ENCODING = "latin-1"
CSV_DELIMITER = ";"


def build_fca_archive_url(year: int) -> str:
    return FCA_ARCHIVE_URL_TEMPLATE.format(year=year)


def build_securities_filename(year: int) -> str:
    return SECURITIES_FILENAME_TEMPLATE.format(year=year)


def _rows(raw: bytes):
    return csv.DictReader(
        io.StringIO(raw.decode(CSV_ENCODING)), delimiter=CSV_DELIMITER,
    )


def _download(url: str) -> bytes:
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def download_fca_archive(year: int) -> bytes:
    return _download(build_fca_archive_url(year))


def download_company_registry() -> bytes:
    return _download(COMPANY_REGISTRY_URL)


def _optional_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def parse_fca_securities(archive_bytes: bytes, year: int) -> list[SecurityListing]:
    """Every security in one FCA archive that carries a trading code."""
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        try:
            raw = archive.read(build_securities_filename(year))
        except KeyError:
            logger.warning("FCA archive for %s has no securities table", year)
            return []

    listings = []
    for row in _rows(raw):
        ticker = (row.get("Codigo_Negociacao") or "").strip().upper()
        if not ticker:
            continue
        listings.append(SecurityListing(
            ticker=ticker,
            cnpj=(row.get("CNPJ_Companhia") or "").strip(),
            company_name=(row.get("Nome_Empresarial") or "").strip(),
            delisted_on=_optional_date(row.get("Data_Fim_Negociacao")),
        ))
    return listings


def parse_company_registry(registry_bytes: bytes) -> list[CompanyRecord]:
    """Every registered company that has a CVM code.

    Companies without one are dropped: the code is what filings are keyed by,
    so an entry lacking it cannot bridge to anything.
    """
    companies = []
    for row in _rows(registry_bytes):
        cvm_code = (row.get("CD_CVM") or "").strip().lstrip("0")
        if not cvm_code:
            continue
        companies.append(CompanyRecord(
            cvm_code=cvm_code,
            cnpj=(row.get("CNPJ_CIA") or "").strip(),
            social_name=(row.get("DENOM_SOCIAL") or "").strip(),
            trade_name=(row.get("DENOM_COMERC") or "").strip(),
        ))
    return companies


def load_security_listings(years: list[int]) -> list[SecurityListing]:
    """Securities across several FCA years, newest listing of a ticker winning.

    Reading years independently and concatenating would make any reassigned
    ticker ambiguous, and ambiguity is treated as absence downstream — so the
    ticker would silently drop out. Taking the newest year that lists a ticker
    keeps its current owner and still recovers companies that last filed an
    FCA some years ago.

    A year that cannot be fetched is logged and skipped rather than failing the
    run: CVM's coverage thins out in the early years, and one missing archive
    should not cost the mapping every other year provides.
    """
    listings_by_ticker: dict[str, SecurityListing] = {}
    for year in sorted(years, reverse=True):
        try:
            archive = download_fca_archive(year)
        except Exception as error:  # noqa: BLE001 - one bad year must not be fatal
            logger.warning("Could not read the FCA archive for %s: %s", year, error)
            continue
        for listing in parse_fca_securities(archive, year):
            listings_by_ticker.setdefault(listing.ticker, listing)
    return list(listings_by_ticker.values())
