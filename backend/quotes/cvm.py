"""Parser for CVM ITR open data (quarterly filings of Brazilian issuers).

BRAPI is the primary source of Brazilian quarterly statements, but it lags the
filing by one to three weeks. The CVM publishes the same filings as open data
within a few days, so this module lets a freshly filed quarter be seeded ahead
of BRAPI. Every account mapping below was calibrated against BRAPI's own stored
values for 2026-03-31 (Gerdau and Petrobras) and reproduces them exactly, so a
CVM-sourced quarter is interchangeable with a BRAPI-sourced one and is safely
overwritten once BRAPI catches up.

Two period conventions matter:

* **Income statement (DRE)** is filed with both a year-to-date column and a
  standalone three-month column, so the quarter can be read directly.
* **Cash flow (DFC)** is filed year-to-date only, so the quarter is the delta
  against the previous quarter's filing in the same annual archive.
* **Balance sheet (BPA/BPP)** is a point-in-time snapshot; no arithmetic.
"""
import csv
import io
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

ONE_DAY = timedelta(days=1)

ITR_ARCHIVE_URL_TEMPLATE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/"
    "itr_cia_aberta_{year}.zip"
)
ITR_INDEX_FILENAME_TEMPLATE = "itr_cia_aberta_{year}.csv"

# The annual DFP, which is where the fourth quarter has to come from. ITR
# covers Q1 to Q3; nobody files Q4 as a standalone period, so it is derived as
# the audited year minus the nine months already reported.
DFP_ARCHIVE_URL_TEMPLATE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
    "dfp_cia_aberta_{year}.zip"
)
ITR_STATEMENT_PREFIX = "itr_cia_aberta"
DFP_STATEMENT_PREFIX = "dfp_cia_aberta"

DOWNLOAD_TIMEOUT_SECONDS = 120
HEAD_TIMEOUT_SECONDS = 30

# The index is the archive's first entry and compresses to roughly 25 KB per
# quarter of filings, so a quarter of a megabyte covers a full year with room
# to spare. A truncated read is detected rather than assumed away (see
# ``_inflate_first_entry``) and the range is widened until the entry is whole.
INDEX_PREFIX_BYTES = 256 * 1024
INDEX_PREFIX_MAX_BYTES = 4 * 1024 * 1024

LOCAL_FILE_HEADER_SIGNATURE = b"PK\x03\x04"
LOCAL_FILE_HEADER_SIZE = 30
LOCAL_HEADER_METHOD_OFFSET = 8
LOCAL_HEADER_NAME_LENGTH_OFFSET = 26
LOCAL_HEADER_EXTRA_LENGTH_OFFSET = 28
DEFLATE_METHOD = 8
RAW_DEFLATE_WINDOW = -zlib.MAX_WBITS

# CVM's standard account taxonomy (CD_CONTA).
ACCOUNT_CURRENT_ASSETS = "1.01"
ACCOUNT_CURRENT_LIABILITIES = "2.01"
ACCOUNT_NONCURRENT_LIABILITIES = "2.02"
ACCOUNT_EQUITY = "2.03"
ACCOUNT_CURRENT_BORROWINGS = "2.01.04"
ACCOUNT_NONCURRENT_BORROWINGS = "2.02.01"
ACCOUNT_CURRENT_LEASE = "2.01.04.03"
ACCOUNT_NONCURRENT_LEASE = "2.02.01.03"
ACCOUNT_TOTAL_ASSETS = "1"
ACCOUNT_TOTAL_LIABILITIES_AND_EQUITY = "2"
ACCOUNT_REVENUE = "3.01"
ACCOUNT_NET_INCOME = "3.11"
ACCOUNT_OPERATING_CASH_FLOW = "6.01"
ACCOUNT_INVESTMENT_CASH_FLOW = "6.02"
ACCOUNT_FINANCING_ACTIVITIES_PREFIX = "6.03."

BORROWINGS_ACCOUNTS = (ACCOUNT_CURRENT_BORROWINGS, ACCOUNT_NONCURRENT_BORROWINGS)
LEASE_ACCOUNTS = (ACCOUNT_CURRENT_LEASE, ACCOUNT_NONCURRENT_LEASE)

# What each account must be called for its number to be trusted. The chart of
# accounts is sector-specific, so the number alone does not identify the
# concept. Normalised with ``_normalize`` (lowercased, accents stripped).
LABEL_CURRENT_ASSETS = "ativo circulante"
LABEL_CURRENT_LIABILITIES = "passivo circulante"
LABEL_NONCURRENT_LIABILITIES = "passivo nao circulante"
LABEL_EQUITY = "patrimonio liquido consolidado"
LABEL_BORROWINGS = "emprestimos e financiamentos"
LABEL_LEASE = "financiamento por arrendamento"

# Words that name borrowings wherever a filer chooses to report them.
BORROWING_KEYWORDS = ("emprestimo", "financiamento", "debenture")
LEASE_KEYWORD = "arrendamento"

# Assets must equal liabilities plus equity. It held for all 414 filers of 2026
# that publish both totals, so a violation means the parse is wrong rather than
# the filing. The tolerance absorbs the rounding CVM's own thousands scale
# introduces without admitting a real discrepancy.
BALANCE_TOLERANCE_FRACTION = 0.001

# ORDEM_EXERC discriminates the current period from the prior-year comparative.
CURRENT_PERIOD_MARKER = "ÚLTIMO"

THOUSANDS_SCALE_MARKER = "MIL"
THOUSANDS_MULTIPLIER = 1000

QUARTER_END_MONTH_DAYS = {(3, 31), (6, 30), (9, 30), (12, 31)}
FOURTH_QUARTER_MONTH = 12

DIVIDEND_KEYWORD = "dividendo"
INTEREST_ON_EQUITY_KEYWORDS = ("juros sobre o capital", "juros sobre capital")
DIVIDEND_INFLOW_KEYWORD = "recebid"


class CvmParseError(Exception):
    """The requested company/period cannot be read from the archive."""


@dataclass
class QuarterStatements:
    """One quarter of consolidated statements, in whole units of the currency."""

    cvm_code: str
    quarter_end: date
    revenue: int | None = None
    net_income: int | None = None
    operating_cash_flow: int | None = None
    investment_cash_flow: int | None = None
    dividends_paid: int | None = None
    total_debt: int | None = None
    total_lease: int | None = None
    total_liabilities: int | None = None
    stockholders_equity: int | None = None
    current_assets: int | None = None
    current_liabilities: int | None = None

    @property
    def is_empty(self) -> bool:
        """True when the archive held no usable line for this company/period."""
        value_fields = [
            field.name for field in fields(self)
            if field.name not in ("cvm_code", "quarter_end")
        ]
        return all(getattr(self, name) is None for name in value_fields)


def build_itr_archive_url(year: int) -> str:
    return ITR_ARCHIVE_URL_TEMPLATE.format(year=year)


def download_itr_archive(year: int) -> bytes:
    """Fetch the annual ITR archive published by the CVM."""
    response = requests.get(
        build_itr_archive_url(year), timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.content


# --- The filing index -------------------------------------------------------
#
# Everything below reads ``itr_cia_aberta_<year>.csv``, the manifest listing
# every filing and the date the CVM received it (DT_RECEB). It answers "what
# has been filed, and when" without parsing a line of accounting.
#
# The CVM does not publish this file on its own; it exists only as the first
# entry inside the annual archive. Since the archive is rebuilt in batch (all
# document datasets carry the same timestamp) and served by an nginx that
# honours conditional requests and byte ranges, the manifest can be polled
# frequently for almost nothing: a HEAD reports whether anything was rebuilt,
# and a ranged read pulls the manifest alone rather than the whole archive.


@dataclass(frozen=True)
class ArchiveState:
    """When the published archive was last rebuilt, as the server reports it."""

    last_modified: datetime | None
    etag: str

    @property
    def is_known(self) -> bool:
        return self.last_modified is not None or bool(self.etag)


@dataclass(frozen=True)
class FilingRecord:
    """One row of the filing index."""

    cvm_code: str
    company_name: str
    cnpj: str
    reference_date: date
    filed_at: date | None
    version: int
    document_id: str


def build_itr_index_filename(year: int) -> str:
    return ITR_INDEX_FILENAME_TEMPLATE.format(year=year)


def fetch_itr_archive_state(year: int) -> ArchiveState:
    """Ask the server when the archive was last rebuilt, downloading nothing.

    This is the cheapest available signal that new filings exist, and the only
    one that reveals the rebuild cadence: successive Last-Modified values are
    the rebuild history.
    """
    response = requests.head(
        build_itr_archive_url(year), timeout=HEAD_TIMEOUT_SECONDS,
    )
    # Fail loudly rather than reporting an unknown build time: the caller reads
    # "unknown" as "possibly new" and would download the whole archive on every
    # poll for the duration of a CVM outage.
    response.raise_for_status()
    return ArchiveState(
        last_modified=_parse_http_date(response.headers.get("Last-Modified")),
        etag=response.headers.get("ETag", ""),
    )


def _parse_http_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _download_prefix(url: str, size: int) -> bytes:
    response = requests.get(
        url,
        headers={"Range": f"bytes=0-{size - 1}"},
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.content


def _inflate_first_entry(prefix: bytes) -> tuple[str, bytes, bool]:
    """Inflate the archive's first entry from a prefix of its bytes.

    Returns the entry's name, whatever inflated, and whether the entry was
    complete. Truncation is reported rather than hidden: half an index looks
    exactly like a quiet week of filings.
    """
    if not prefix.startswith(LOCAL_FILE_HEADER_SIGNATURE):
        raise CvmParseError("Ranged read did not begin with a zip local file header.")

    method = int.from_bytes(prefix[LOCAL_HEADER_METHOD_OFFSET:][:2], "little")
    if method != DEFLATE_METHOD:
        raise CvmParseError(f"Unsupported zip compression method {method}.")

    name_length = int.from_bytes(prefix[LOCAL_HEADER_NAME_LENGTH_OFFSET:][:2], "little")
    extra_length = int.from_bytes(prefix[LOCAL_HEADER_EXTRA_LENGTH_OFFSET:][:2], "little")
    name = prefix[LOCAL_FILE_HEADER_SIZE:][:name_length].decode("cp437")

    body = prefix[LOCAL_FILE_HEADER_SIZE + name_length + extra_length:]
    decompressor = zlib.decompressobj(RAW_DEFLATE_WINDOW)
    return name, decompressor.decompress(body), decompressor.eof


def _index_from_archive(archive_bytes: bytes, filename: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        try:
            return archive.read(filename)
        except KeyError:
            raise CvmParseError(
                f"The ITR archive does not contain the filing index {filename}."
            ) from None


def download_itr_index(year: int) -> bytes:
    """Fetch the filing index alone, by ranged read of the archive.

    Falls back to the full download whenever the archive's layout is not the
    one this shortcut assumes. The fallback is slow, not wrong, so an unexpected
    layout costs bandwidth rather than correctness.
    """
    filename = build_itr_index_filename(year)
    url = build_itr_archive_url(year)

    size = INDEX_PREFIX_BYTES
    while size <= INDEX_PREFIX_MAX_BYTES:
        prefix = _download_prefix(url, size)
        try:
            name, data, is_complete = _inflate_first_entry(prefix)
        except (CvmParseError, zlib.error):
            break
        if name != filename:
            break
        if is_complete:
            return data
        if len(prefix) < size:
            break  # The server sent everything it had; a wider range cannot help.
        size *= 2

    return _index_from_archive(download_itr_archive(year), filename)


def parse_itr_index(index_bytes: bytes) -> list[FilingRecord]:
    """Turn the index CSV into filing records, newest version included."""
    reader = csv.DictReader(
        io.TextIOWrapper(io.BytesIO(index_bytes), encoding="latin-1"), delimiter=";",
    )
    return [
        _filing_record(row) for row in reader if (row.get("DT_REFER") or "").strip()
    ]


def _filing_record(row: dict) -> FilingRecord:
    return FilingRecord(
        cvm_code=row["CD_CVM"].strip().lstrip("0") or "0",
        company_name=row.get("DENOM_CIA", "").strip(),
        cnpj=row.get("CNPJ_CIA", "").strip(),
        reference_date=date.fromisoformat(row["DT_REFER"].strip()),
        filed_at=_optional_date(row.get("DT_RECEB")),
        version=int(row.get("VERSAO") or 1),
        document_id=row.get("ID_DOC", "").strip(),
    )


def _optional_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    return date.fromisoformat(raw) if raw else None


def _normalize(text: str) -> str:
    """Lowercase and strip accents so description matching is robust."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _quarter_start(quarter_end: date) -> date:
    return date(quarter_end.year, quarter_end.month - 2, 1)


def previous_quarter_end(quarter_end: date) -> date:
    return _quarter_start(quarter_end) - ONE_DAY


def _year_start(quarter_end: date) -> date:
    return date(quarter_end.year, 1, 1)


def _scaled_amount(row: dict) -> int:
    """Convert VL_CONTA to whole currency units, honouring ESCALA_MOEDA."""
    amount = float(row["VL_CONTA"])
    if row.get("ESCALA_MOEDA", "").strip().upper() == THOUSANDS_SCALE_MARKER:
        amount *= THOUSANDS_MULTIPLIER
    return int(round(amount))


def _statement_rows(archive: zipfile.ZipFile, filename: str):
    """Yield the current-period rows of the latest version of each document."""
    try:
        raw = archive.read(filename)
    except KeyError:
        return

    reader = csv.DictReader(
        io.TextIOWrapper(io.BytesIO(raw), encoding="latin-1"), delimiter=";",
    )
    rows = [row for row in reader if row.get("ORDEM_EXERC") == CURRENT_PERIOD_MARKER]

    latest_version: dict[tuple[str, str], int] = {}
    for row in rows:
        document = (row["CD_CVM"], row["DT_REFER"])
        version = int(row["VERSAO"])
        if version > latest_version.get(document, -1):
            latest_version[document] = version

    for row in rows:
        document = (row["CD_CVM"], row["DT_REFER"])
        if int(row["VERSAO"]) == latest_version[document]:
            yield row


def _company_rows(archive: zipfile.ZipFile, filename: str, cvm_code: str) -> list[dict]:
    wanted = cvm_code.lstrip("0")
    return [
        row for row in _statement_rows(archive, filename)
        if row["CD_CVM"].lstrip("0") == wanted
    ]


def _index_flows(rows: list[dict]) -> dict[tuple[str, date, date], int]:
    """Key flow-statement rows by (account, period start, period end)."""
    indexed: dict[tuple[str, date, date], int] = {}
    for row in rows:
        start = date.fromisoformat(row["DT_INI_EXERC"])
        end = date.fromisoformat(row["DT_FIM_EXERC"])
        indexed[(row["CD_CONTA"], start, end)] = _scaled_amount(row)
    return indexed


@dataclass(frozen=True)
class BalanceLine:
    """One balance-sheet line: what it is called as well as what it is worth."""

    amount: int
    label: str


def _index_balances(rows: list[dict], quarter_end: date) -> dict[str, BalanceLine]:
    """Key balance-sheet rows by account, keeping only the quarter-end snapshot.

    The label travels with the amount because the account number alone does not
    identify the concept · see ``_labelled_amount``.
    """
    return {
        row["CD_CONTA"]: BalanceLine(
            amount=_scaled_amount(row), label=_normalize(row.get("DS_CONTA", "")),
        )
        for row in rows
        if date.fromisoformat(row["DT_FIM_EXERC"]) == quarter_end
    }


def _labelled_amount(
    balances: dict[str, BalanceLine], account: str, expected_label: str,
) -> int | None:
    """The amount at an account, but only when the line says what we assume.

    The chart of accounts is sector-specific: 2.02.01 is "Empréstimos e
    Financiamentos" for 516 filers and "Depósitos" for the banks, 2.01 is
    "Passivo Circulante" for most and a fair-value financial liability for
    others. Reading by number alone turns a bank's customer deposits into debt
    and its provisions into equity, which is not a mislabelled field but a
    different quantity entirely.
    """
    line = balances.get(account)
    if line is None or line.label != expected_label:
        return None
    return line.amount


def _sum_labelled(
    balances: dict[str, BalanceLine], accounts: tuple[str, ...], expected_label: str,
) -> int | None:
    amounts = [
        amount for amount in (
            _labelled_amount(balances, account, expected_label)
            for account in accounts
        )
        if amount is not None
    ]
    return sum(amounts) if amounts else None


def _equity(balances: dict[str, BalanceLine]) -> int | None:
    """Equity, found by the line that claims to be equity.

    All 416 consolidated filers of 2026 carry a "Patrimônio Líquido
    Consolidado" line, but they put it at 2.03 (404), 2.07 (7) or 2.08 (5).
    The label is the reliable key; the account number is not.
    """
    matches = [
        line.amount for line in balances.values() if line.label == LABEL_EQUITY
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise CvmParseError(
            f"{len(matches)} lines claim to be equity; refusing to guess which "
            f"one every leverage ratio should be divided by."
        )
    return matches[0]


def _quarter_flow(
    flows: dict[tuple[str, date, date], int], account: str, quarter_end: date,
) -> int | None:
    """Return one quarter of a flow account, differencing YTD when needed."""
    quarter_start = _quarter_start(quarter_end)
    year_start = _year_start(quarter_end)

    standalone = flows.get((account, quarter_start, quarter_end))
    if standalone is not None:
        return standalone

    year_to_date = flows.get((account, year_start, quarter_end))
    if year_to_date is None:
        return None
    if quarter_start == year_start:
        return year_to_date

    previous_year_to_date = flows.get(
        (account, year_start, previous_quarter_end(quarter_end))
    )
    if previous_year_to_date is None:
        return None
    return year_to_date - previous_year_to_date


def _is_dividend_payment(description: str) -> bool:
    normalized = _normalize(description)
    if DIVIDEND_INFLOW_KEYWORD in normalized:
        return False
    if DIVIDEND_KEYWORD in normalized:
        return True
    return any(keyword in normalized for keyword in INTEREST_ON_EQUITY_KEYWORDS)


def _dividend_accounts(rows: list[dict]) -> set[str]:
    return {
        row["CD_CONTA"] for row in rows
        if row["CD_CONTA"].startswith(ACCOUNT_FINANCING_ACTIVITIES_PREFIX)
        and _is_dividend_payment(row["DS_CONTA"])
    }


def _quarter_dividends(
    rows: list[dict], flows: dict[tuple[str, date, date], int], quarter_end: date,
) -> int | None:
    amounts = [
        _quarter_flow(flows, account, quarter_end)
        for account in sorted(_dividend_accounts(rows))
    ]
    resolved = [amount for amount in amounts if amount is not None]
    if not resolved:
        return None
    return sum(resolved)


def _sum_present(balances: dict[str, int], *accounts: str) -> int | None:
    """Sum the accounts that are present; None when none of them are."""
    values = [balances[account] for account in accounts if account in balances]
    if not values:
        return None
    return sum(values)


def _borrowings_reported_elsewhere(balances: dict[str, BalanceLine]) -> bool:
    """Does a non-zero line outside the standard accounts name borrowings?

    Some filers publish the standard borrowings accounts as zeros from the
    fixed template and report the real figure under "Outras Obrigações" with a
    descriptive label · Allos carries R$5.6bn at 2.02.02.02.07, "Empréstimos,
    financiamentos e debêntures", while 2.01.04 and 2.02.01 are both 0.

    Leases are excluded: "Financiamento por Arrendamento" contains the word
    financiamento but is tracked separately.
    """
    for account, line in balances.items():
        if account in BORROWINGS_ACCOUNTS or not line.amount:
            continue
        if LEASE_KEYWORD in line.label:
            continue
        if any(keyword in line.label for keyword in BORROWING_KEYWORDS):
            return True
    return False


def _debt_total(balances: dict[str, BalanceLine]) -> int | None:
    """Borrowings, or None when the filing does not let us say.

    A zero that is contradicted by a borrowings line elsewhere is not a
    debt-free balance sheet, it is a presentation this parser cannot total
    reliably. Saying nothing is right; saying zero would show a leveraged
    company as carrying none.
    """
    total = _sum_labelled(balances, BORROWINGS_ACCOUNTS, LABEL_BORROWINGS)
    if total == 0 and _borrowings_reported_elsewhere(balances):
        return None
    return total


def _lease_total(balances: dict[str, BalanceLine]) -> int | None:
    """Leases default to 0 once a borrowings line exists but no lease line does."""
    lease = _sum_labelled(balances, LEASE_ACCOUNTS, LABEL_LEASE)
    if lease is not None:
        return lease
    has_borrowings = _sum_labelled(
        balances, BORROWINGS_ACCOUNTS, LABEL_BORROWINGS,
    ) is not None
    return 0 if has_borrowings else None


def _total_liabilities(
    balances: dict[str, BalanceLine], equity: int | None,
) -> int | None:
    """Everything owed, excluding equity.

    Preferred as the balance-sheet total less equity, which is defined for
    every filer. It agrees with the current-plus-non-current sum for all 404
    industrial filers of 2026, and unlike that sum it is also meaningful for a
    bank, whose 2.01 and 2.02 are fair-value and amortised-cost financial
    liabilities rather than a maturity split.

    Falls back to the sum for filings that omit the root line.
    """
    total = balances.get(ACCOUNT_TOTAL_LIABILITIES_AND_EQUITY)
    if total is not None and equity is not None:
        return total.amount - equity

    current = _labelled_amount(
        balances, ACCOUNT_CURRENT_LIABILITIES, LABEL_CURRENT_LIABILITIES,
    )
    noncurrent = _labelled_amount(
        balances, ACCOUNT_NONCURRENT_LIABILITIES, LABEL_NONCURRENT_LIABILITIES,
    )
    parts = [part for part in (current, noncurrent) if part is not None]
    return sum(parts) if parts else None


def _validate_balance_sheet(balances: dict[str, BalanceLine]) -> None:
    """Refuse a parse whose balance sheet does not balance.

    Assets equal liabilities plus equity for every filer that publishes both
    totals · 414 of 414 in 2026 · so a mismatch means this parse has picked up
    the wrong rows, not that the company filed something impossible. Refusing
    is the point: the failure mode these accounts produce is a plausible wrong
    number, and those outlive an exception by a long way.
    """
    assets = balances.get(ACCOUNT_TOTAL_ASSETS)
    total = balances.get(ACCOUNT_TOTAL_LIABILITIES_AND_EQUITY)
    if assets is None or total is None or not assets.amount:
        return

    drift = abs(assets.amount - total.amount) / abs(assets.amount)
    if drift > BALANCE_TOLERANCE_FRACTION:
        raise CvmParseError(
            f"The balance sheet does not balance: total assets "
            f"{assets.amount:,} against liabilities plus equity "
            f"{total.amount:,} ({drift:.1%} apart)."
        )


def validate_quarter_end(quarter_end: date) -> None:
    if (quarter_end.month, quarter_end.day) not in QUARTER_END_MONTH_DAYS:
        raise CvmParseError(
            f"{quarter_end} is not a quarter end (expected 03-31, 06-30, "
            f"09-30 or 12-31)."
        )
    if quarter_end.month == FOURTH_QUARTER_MONTH:
        raise CvmParseError(
            "The fourth quarter is not filed as an ITR; it must be derived "
            "from the annual DFP archive."
        )


def _statement_sets(archive, prefix: str, year: int, cvm_code: str):
    """The four statement row sets one company filed, from either archive.

    ITR and DFP publish the same five files under different prefixes, so the
    account mapping, label guards and balance checks apply unchanged to both.
    """
    income = _company_rows(archive, f"{prefix}_DRE_con_{year}.csv", cvm_code)
    cash_flow = _company_rows(archive, f"{prefix}_DFC_MI_con_{year}.csv", cvm_code)
    if not cash_flow:
        cash_flow = _company_rows(archive, f"{prefix}_DFC_MD_con_{year}.csv", cvm_code)
    assets = _company_rows(archive, f"{prefix}_BPA_con_{year}.csv", cvm_code)
    liabilities = _company_rows(archive, f"{prefix}_BPP_con_{year}.csv", cvm_code)
    return income, cash_flow, assets, liabilities


def build_dfp_archive_url(year: int) -> str:
    return DFP_ARCHIVE_URL_TEMPLATE.format(year=year)


class DfpArchiveNotPublished(Exception):
    """The CVM has not put a given year's DFP archive online yet.

    Distinct from a transport failure on purpose. This job necessarily runs
    for a reporting year before the CVM publishes it, so a 404 here is the
    expected state for part of every year, and the caller should say so and
    stop rather than treat it as a fault.
    """


def download_dfp_archive(year: int) -> bytes:
    """Fetch the annual DFP archive published by the CVM.

    Raises :class:`DfpArchiveNotPublished` when the archive is not online
    yet. Every other HTTP failure is re-raised untouched, because a 500 or a
    timeout is a genuine problem worth waking someone for.
    """
    response = requests.get(
        build_dfp_archive_url(year), timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        raise DfpArchiveNotPublished(
            f"CVM has not published the {year} DFP archive yet "
            f"({build_dfp_archive_url(year)})",
        )
    response.raise_for_status()
    return response.content


def extract_annual_statements(
    archive_bytes: bytes, cvm_code: str, year: int,
) -> QuarterStatements:
    """Read one company's audited year from the DFP.

    Flows cover the calendar year exactly. Filers on a non-calendar fiscal year
    publish trailing-twelve-month windows against the same document, and those
    are not the year · taking any twelve-month window would silently mix a
    March-ending year into a December one.

    The balance sheet is the 31 December snapshot, filed directly. Only the
    flows ever need arithmetic, and that happens downstream where the nine
    months already reported are known.
    """
    year_end = date(year, 12, 31)
    archive = zipfile.ZipFile(io.BytesIO(archive_bytes))

    income_rows, cash_flow_rows, asset_rows, liability_rows = _statement_sets(
        archive, DFP_STATEMENT_PREFIX, year, cvm_code,
    )

    income_flows = _index_flows(income_rows)
    cash_flows = _index_flows(cash_flow_rows)
    balances = _index_balances(asset_rows + liability_rows, year_end)
    _validate_balance_sheet(balances)
    equity = _equity(balances)

    year_window = (date(year, 1, 1), year_end)

    def over_the_year(flows, account):
        return flows.get((account, *year_window))

    return QuarterStatements(
        cvm_code=cvm_code,
        quarter_end=year_end,
        revenue=over_the_year(income_flows, ACCOUNT_REVENUE),
        net_income=over_the_year(income_flows, ACCOUNT_NET_INCOME),
        operating_cash_flow=over_the_year(cash_flows, ACCOUNT_OPERATING_CASH_FLOW),
        investment_cash_flow=over_the_year(cash_flows, ACCOUNT_INVESTMENT_CASH_FLOW),
        dividends_paid=_annual_dividends(cash_flow_rows, cash_flows, year_window),
        total_debt=_debt_total(balances),
        total_lease=_lease_total(balances),
        total_liabilities=_total_liabilities(balances, equity),
        stockholders_equity=equity,
        current_assets=_labelled_amount(
            balances, ACCOUNT_CURRENT_ASSETS, LABEL_CURRENT_ASSETS,
        ),
        current_liabilities=_labelled_amount(
            balances, ACCOUNT_CURRENT_LIABILITIES, LABEL_CURRENT_LIABILITIES,
        ),
    )


def _annual_dividends(rows, flows, year_window) -> int | None:
    amounts = [
        flows.get((account, *year_window))
        for account in sorted(_dividend_accounts(rows))
    ]
    resolved = [amount for amount in amounts if amount is not None]
    return sum(resolved) if resolved else None


def extract_quarter_statements(
    archive_bytes: bytes, cvm_code: str, quarter_end: date,
) -> QuarterStatements:
    """Read one company's consolidated statements for a single quarter."""
    validate_quarter_end(quarter_end)

    year = quarter_end.year
    archive = zipfile.ZipFile(io.BytesIO(archive_bytes))

    income_rows, cash_flow_rows, asset_rows, liability_rows = _statement_sets(
        archive, ITR_STATEMENT_PREFIX, year, cvm_code,
    )

    return build_quarter_statements(
        income_rows, cash_flow_rows, asset_rows, liability_rows,
        cvm_code=cvm_code, quarter_end=quarter_end,
    )


def build_quarter_statements(
    income_rows: list[dict],
    cash_flow_rows: list[dict],
    asset_rows: list[dict],
    liability_rows: list[dict],
    *,
    cvm_code: str,
    quarter_end: date,
) -> QuarterStatements:
    """Turn statement rows into one quarter, whatever produced the rows.

    The rows follow the open-data CSV vocabulary (CD_CONTA, DS_CONTA,
    VL_CONTA, ESCALA_MOEDA, DT_INI_EXERC, DT_FIM_EXERC), which makes this the
    meeting point for the two publication formats: the consolidated annual
    archive and the per-filing ENET package parsed by ``cvm_enet``. Every
    label guard, the balance validation and the year-to-date differencing
    apply identically to both.
    """
    income_flows = _index_flows(income_rows)
    cash_flows = _index_flows(cash_flow_rows)
    balances = _index_balances(asset_rows + liability_rows, quarter_end)
    _validate_balance_sheet(balances)
    equity = _equity(balances)

    return QuarterStatements(
        cvm_code=cvm_code,
        quarter_end=quarter_end,
        revenue=_quarter_flow(income_flows, ACCOUNT_REVENUE, quarter_end),
        net_income=_quarter_flow(income_flows, ACCOUNT_NET_INCOME, quarter_end),
        operating_cash_flow=_quarter_flow(
            cash_flows, ACCOUNT_OPERATING_CASH_FLOW, quarter_end,
        ),
        investment_cash_flow=_quarter_flow(
            cash_flows, ACCOUNT_INVESTMENT_CASH_FLOW, quarter_end,
        ),
        dividends_paid=_quarter_dividends(cash_flow_rows, cash_flows, quarter_end),
        total_debt=_debt_total(balances),
        total_lease=_lease_total(balances),
        total_liabilities=_total_liabilities(balances, equity),
        stockholders_equity=equity,
        current_assets=_labelled_amount(
            balances, ACCOUNT_CURRENT_ASSETS, LABEL_CURRENT_ASSETS,
        ),
        current_liabilities=_labelled_amount(
            balances, ACCOUNT_CURRENT_LIABILITIES, LABEL_CURRENT_LIABILITIES,
        ),
    )
