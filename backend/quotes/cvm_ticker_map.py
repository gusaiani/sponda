"""Resolve a B3 ticker to the CVM code that keys its filings.

The CVM identifies companies by ``CD_CVM`` and CNPJ and never by ticker, so
nothing can be read from CVM for a given company until this bridge exists.

Three sources of evidence, strongest first:

1. **The published ticker.** The FCA securities table carries
   ``Codigo_Negociacao`` against a CNPJ. Authoritative when well-formed, and
   covers the large majority of the universe.
2. **The ticker root.** B3 gives one company one four-letter root (KLBN3,
   KLBN4, KLBN11), and the FCA sometimes lists only the unit. Used only when
   the root belongs to exactly one company.
3. **The company name**, normalised for the rendering differences between the
   two datasets (``BCO``/``BANCO``, ``S.A.``/``SA``/``S/A``, accents, and the
   ``- EM RECUPERAÇÃO JUDICIAL`` suffix the registry appends).

The published field is dirty in ways that matter. Of the values CVM publishes
as ``Codigo_Negociacao``, dozens are not tickers at all: zeros, a debenture
code like ``1545-8``, and for CSN the company's own CVM code ``4030`` sitting
in the ticker column. Reading that field without validating it attaches real
tickers to whichever company published the string, so every candidate is
checked against the B3 ticker shape first. Refusing to map is a gap; mapping
to the wrong company is a wrong number on the site.

For the same reason every strategy declines on ambiguity rather than guessing,
and the method that produced a mapping is recorded so a disputed figure can be
traced back to the evidence behind it.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

# B3 tickers are four letters and one or two digits: PETR4, KLBN11, BPAC11.
B3_TICKER_PATTERN = re.compile(r"^[A-Z]{4}\d{1,2}$")
TICKER_ROOT_LENGTH = 4

MATCH_TICKER = "ticker"
MATCH_ROOT = "root"
MATCH_NAME = "name"
MATCH_MANUAL = "manual"

MATCH_METHOD_CHOICES = [
    (MATCH_TICKER, "Published trading code (FCA)"),
    (MATCH_ROOT, "Ticker root shared with a published code"),
    (MATCH_NAME, "Normalised company name"),
    (MATCH_MANUAL, "Set by hand"),
]

RECOVERY_SUFFIX = " - EM RECUPERACAO"
COMPANY_FORM_SUBSTITUTIONS = (
    (re.compile(r"\bBCO\b"), "BANCO"),
    (re.compile(r"\bCIA\b"), "COMPANHIA"),
    (re.compile(r"\bDISTRIB\b"), "DISTRIBUIDORA"),
    (re.compile(r"\bPART\b"), "PARTICIPACOES"),
)


@dataclass(frozen=True)
class SecurityListing:
    """One security the FCA lists for a company."""

    ticker: str
    cnpj: str
    company_name: str = ""
    delisted_on: date | None = None


@dataclass(frozen=True)
class CompanyRecord:
    """One company in the CVM registry."""

    cvm_code: str
    cnpj: str
    social_name: str = ""
    trade_name: str = ""


@dataclass(frozen=True)
class TickerMatch:
    cvm_code: str
    cnpj: str
    method: str


def normalize_company_name(name: str | None) -> str:
    """Render a company name the way both datasets can agree on.

    The registry and the ticker universe disagree on abbreviation, accents,
    corporate form and bankruptcy suffixes for the same company, so the raw
    strings match for barely half of them.
    """
    text = unicodedata.normalize("NFKD", (name or "").upper())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.split(RECOVERY_SUFFIX)[0]
    text = text.replace("S/A", " SA ").replace("S.A.", " SA ").replace("S.A", " SA ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = " ".join(text.split())
    for pattern, replacement in COMPANY_FORM_SUBSTITUTIONS:
        text = pattern.sub(replacement, text)
    return " ".join(text.split())


def is_b3_ticker(symbol: str | None) -> bool:
    return bool(B3_TICKER_PATTERN.match((symbol or "").strip().upper()))


class TickerResolver:
    """Resolves tickers against one snapshot of the CVM's published data."""

    def __init__(
        self, listings: list[SecurityListing], companies: list[CompanyRecord],
    ):
        self._company_by_cnpj = {
            company.cnpj: company for company in companies if company.cnpj
        }
        self._companies_by_name = self._index_by_name(companies)
        self._companies_by_ticker, self._companies_by_root = self._index_listings(
            listings
        )

    @staticmethod
    def _index_by_name(
        companies: list[CompanyRecord],
    ) -> dict[str, set[CompanyRecord]]:
        indexed: dict[str, set[CompanyRecord]] = defaultdict(set)
        for company in companies:
            for raw_name in (company.social_name, company.trade_name):
                name = normalize_company_name(raw_name)
                if name:
                    indexed[name].add(company)
        return indexed

    def _index_listings(
        self, listings: list[SecurityListing],
    ) -> tuple[dict[str, set[CompanyRecord]], dict[str, set[CompanyRecord]]]:
        by_ticker: dict[str, set[CompanyRecord]] = defaultdict(set)
        by_root: dict[str, set[CompanyRecord]] = defaultdict(set)
        for listing in listings:
            ticker = (listing.ticker or "").strip().upper()
            if not is_b3_ticker(ticker):
                continue
            company = self._company_by_cnpj.get(listing.cnpj)
            if company is None:
                continue
            by_ticker[ticker].add(company)
            by_root[ticker[:TICKER_ROOT_LENGTH]].add(company)
        return by_ticker, by_root

    def resolve(self, symbol: str, company_name: str | None = None):
        """The strongest available match, or None when the evidence is thin."""
        ticker = (symbol or "").strip().upper()
        if not is_b3_ticker(ticker):
            return None

        for method, company in (
            (MATCH_TICKER, _sole(self._companies_by_ticker.get(ticker))),
            (MATCH_ROOT, _sole(self._companies_by_root.get(
                ticker[:TICKER_ROOT_LENGTH]
            ))),
            (MATCH_NAME, self._by_name(company_name)),
        ):
            if company is not None:
                return TickerMatch(
                    cvm_code=company.cvm_code, cnpj=company.cnpj, method=method,
                )
        return None

    def _by_name(self, company_name: str | None) -> CompanyRecord | None:
        name = normalize_company_name(company_name)
        if not name:
            return None
        return _sole(self._companies_by_name.get(name))


def _sole(candidates: set[CompanyRecord] | None) -> CompanyRecord | None:
    """The single candidate, or None when there are none or several.

    Ambiguity is treated as absence throughout: a ticker attached to the wrong
    company produces a plausible wrong number, which survives review far longer
    than a missing one.
    """
    if not candidates or len(candidates) > 1:
        return None
    return next(iter(candidates))
