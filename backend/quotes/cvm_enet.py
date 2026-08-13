"""Read a single ITR filing straight from CVM's ENET system.

The consolidated open-data archive that ``cvm.py`` parses is rebuilt roughly
weekly, so a quarter filed the day after a rebuild waits days before the
archive path can see it. ENET (rad.cvm.gov.br) is the system companies file
into, and its public search lists a filing within minutes of delivery. This
module turns that listing and the filing's own package into the same
``QuarterStatements`` the archive parser produces, through the same account
vocabulary, label guards and balance validation (``cvm.build_quarter_statements``).

Two format differences from the archive matter:

* **The income statement** carries a standalone three-month column, so the
  quarter is read directly, exactly as in the archive.
* **The cash flow is year-to-date only**, and unlike the archive a single
  package holds no earlier filings to difference against. The previous
  quarter's package is downloaded as well (second and third quarters only),
  so the delta stays pure CVM arithmetic rather than mixing sources.

The server behind ENET requires a session cookie from the search page and a
browser User-Agent; without the latter its WAF resets large downloads
mid-transfer.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
import zipfile
import io
from dataclasses import dataclass
from datetime import date, datetime

import requests
from urllib3.util.retry import Retry

from .cvm import (
    CvmParseError,
    QuarterStatements,
    validate_quarter_end,
    build_quarter_statements,
)

ENET_BASE_URL = "https://www.rad.cvm.gov.br/ENET"
SEARCH_PAGE_URL = f"{ENET_BASE_URL}/frmConsultaExternaCVM.aspx"
SEARCH_API_URL = f"{SEARCH_PAGE_URL}/ListarDocumentos"
DOWNLOAD_URL_TEMPLATE = (
    f"{ENET_BASE_URL}/frmDownloadDocumento.aspx"
    "?Tela=ext&numSequencia={document_number}&numVersao={version}"
    "&numProtocolo={protocol}&descTipo=ITR&CodigoInstituicao=1"
)

# ENET's category code for structured quarterly filings (ITR). The codes are
# not documented; EST_3 was established by probing the search endpoint and
# reading the categories of what came back.
QUARTERLY_FILINGS_CATEGORY = "EST_3"

# Without a browser-like User-Agent the WAF in front of rad.cvm.gov.br resets
# multi-megabyte downloads partway through, leaving a truncated zip.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
)

SEARCH_TIMEOUT_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 300

# The server drops connections without warning · reusing a keep-alive socket
# for a second multi-megabyte download is reliably reset. Retries absorb the
# drops; Connection: close on downloads avoids provoking them.
CONNECTION_RETRIES = Retry(total=3, backoff_factor=1)

ROW_SEPARATOR = "&*"
FIELD_SEPARATOR = "$&"
ACTIVE_STATUS = "Ativo"
ITR_DOWNLOAD_KIND = "ITR"

FIELD_COUNT = 11
CVM_CODE_FIELD = 0
COMPANY_NAME_FIELD = 1
REFERENCE_DATE_FIELD = 5
DELIVERY_FIELD = 6
STATUS_FIELD = 7
VERSION_FIELD = 8
ACTIONS_FIELD = 10

# <spanOrder>20260630</spanOrder> 30/06/2026 — the sortable date the grid
# embeds is easier to read than the display date next to it.
SORTABLE_DATE_PATTERN = re.compile(r"<spanOrder>(\d{8})</spanOrder>")
DOWNLOAD_CALL_PATTERN = re.compile(
    r"OpenDownloadDocumentos\('([^']+)','([^']+)','([^']+)','([^']+)'\)"
)

STATEMENTS_ROOT_TAG = "XmlInformacoesTrimestraisFinanceiras"

# CodigoEscalaMoeda enumerates the filing's currency scale. 2 is thousands,
# verified against BRAPI's stored values for the same quarter; 1 is whole
# units. Anything else is refused rather than guessed, because a misread
# scale is off by a factor of a thousand and perfectly plausible on a page.
SCALE_CODE_TO_CSV_MARKER = {"1": "UNIDADE", "2": "MIL"}

# 1.458.278 or -3.848 · dots are thousands separators. Per-share lines carry
# a comma decimal (0,3821); those accounts are never read downstream but must
# still parse, because rows are built for every account in a statement.
DOTTED_AMOUNT_PATTERN = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?")

ENET_DATE_FORMAT = "%d/%m/%Y"

INCOME_SECTION = "DemonstracaoResultado"
CASH_FLOW_SECTION = "DemonstracaoFluxoCaixa"
ASSETS_SECTION = "BalancoPatrimonialAtivo"
LIABILITIES_SECTION = "BalancoPatrimonialPassivo"

QUARTER_COLUMN = "TrimestreAtual"
INCOME_YEAR_TO_DATE_COLUMN = "AcumuladoExercicioAtual"
CASH_FLOW_YEAR_TO_DATE_COLUMN = "AcumuladoAtualExercicio"


@dataclass(frozen=True)
class EnetFiling:
    """One structured quarterly filing as ENET's search lists it."""

    cvm_code: str
    company_name: str
    reference_date: date
    filed_at: date
    version: int
    document_number: str
    protocol: str


def build_search_payload(start: date, end: date) -> dict:
    """The ListarDocumentos request body for a delivery-date window.

    The endpoint filters on when documents were delivered, not the period
    they report on. Every "-1" means "no filter"; the empresa field is left
    empty because its matching rules are undocumented and filtering by
    company is trivial on the parsed result instead.
    """
    return {
        "dataDe": start.strftime(ENET_DATE_FORMAT),
        "dataAte": end.strftime(ENET_DATE_FORMAT),
        "empresa": "",
        "setorAtividade": "-1",
        "categoriaEmissor": "-1",
        "situacaoEmissor": "-1",
        "tipoParticipante": "-1",
        "dataReferencia": "",
        "categoria": QUARTERLY_FILINGS_CATEGORY,
        "periodo": "2",
        "horaIni": "",
        "horaFim": "",
        "palavraChave": "",
        "ultimaDtRef": "false",
        "tipoEmpresa": "0",
        "token": "",
        "versaoCaptcha": "",
    }


def open_enet_session() -> requests.Session:
    """A session ENET will answer: page cookies plus a browser User-Agent.

    The search endpoint echoes its own schema instead of results when called
    without the cookies the search page sets.
    """
    session = requests.Session()
    session.headers["User-Agent"] = BROWSER_USER_AGENT
    session.mount(
        "https://", requests.adapters.HTTPAdapter(max_retries=CONNECTION_RETRIES),
    )
    response = session.get(SEARCH_PAGE_URL, timeout=SEARCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    return session


def search_itr_filings(
    start: date, end: date, session: requests.Session | None = None,
) -> list[EnetFiling]:
    """Every active quarterly filing ENET lists as delivered in the window."""
    session = session or open_enet_session()
    response = session.post(
        SEARCH_API_URL,
        json=build_search_payload(start, end),
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": SEARCH_PAGE_URL},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()["d"]
    if body.get("temErro"):
        raise CvmParseError(f"ENET search failed: {body.get('msgErro')}")
    return parse_search_results(body.get("dados") or "")


def parse_search_results(grid: str) -> list[EnetFiling]:
    """Read ENET's field-delimited search grid into filing records.

    Rows without a working ITR download link are dropped: a row the grid
    cannot serve a package for cannot be ingested, whatever else it says.
    """
    filings = []
    for row in grid.split(ROW_SEPARATOR):
        fields = row.split(FIELD_SEPARATOR)
        if len(fields) < FIELD_COUNT:
            continue
        filing = _filing_from_fields(fields)
        if filing is not None:
            filings.append(filing)
    return filings


def _filing_from_fields(fields: list[str]) -> EnetFiling | None:
    if fields[STATUS_FIELD].strip() != ACTIVE_STATUS:
        return None
    download = DOWNLOAD_CALL_PATTERN.search(fields[ACTIONS_FIELD])
    if download is None:
        return None
    document_number, version, protocol, kind = download.groups()
    if kind != ITR_DOWNLOAD_KIND:
        return None

    reference_date = _sortable_date(fields[REFERENCE_DATE_FIELD])
    filed_at = _sortable_date(fields[DELIVERY_FIELD])
    if reference_date is None or filed_at is None:
        return None

    return EnetFiling(
        cvm_code=_normalize_cvm_code(fields[CVM_CODE_FIELD]),
        company_name=fields[COMPANY_NAME_FIELD].strip(),
        reference_date=reference_date,
        filed_at=filed_at,
        version=int(version),
        document_number=document_number,
        protocol=protocol,
    )


def _sortable_date(field: str) -> date | None:
    match = SORTABLE_DATE_PATTERN.search(field)
    if match is None:
        return None
    raw = match.group(1)
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def _normalize_cvm_code(raw: str) -> str:
    """02533-0 → 25330, the form Ticker.cvm_code and the archive index use."""
    digits = re.sub(r"\D", "", raw)
    return digits.lstrip("0") or "0"


def latest_filings(filings: list[EnetFiling]) -> list[EnetFiling]:
    """One filing per company and quarter: the highest version wins.

    A restatement supersedes the original wholesale, so parsing anything but
    the latest version would ingest figures the company itself withdrew.
    """
    latest: dict[tuple[str, date], EnetFiling] = {}
    for filing in filings:
        key = (filing.cvm_code, filing.reference_date)
        current = latest.get(key)
        if current is None or filing.version > current.version:
            latest[key] = filing
    return list(latest.values())


def build_download_url(filing: EnetFiling) -> str:
    return DOWNLOAD_URL_TEMPLATE.format(
        document_number=filing.document_number,
        version=filing.version,
        protocol=filing.protocol,
    )


def download_filing_package(
    filing: EnetFiling, session: requests.Session | None = None,
) -> bytes:
    session = session or open_enet_session()
    response = session.get(
        build_download_url(filing),
        headers={"Connection": "close"},
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.content


# --- The filing package -----------------------------------------------------


def extract_quarter_statements_from_package(
    package_bytes: bytes,
    cvm_code: str,
    quarter_end: date,
    previous_package_bytes: bytes | None = None,
) -> QuarterStatements:
    """Read one quarter from a filing package, the archive parser's way.

    The package's statements are converted into rows in the open-data CSV
    vocabulary and handed to ``cvm.build_quarter_statements``, so both
    publication formats pass through identical account mapping and guards.

    ``previous_package_bytes`` supplies the previous quarter's filing, whose
    year-to-date cash flow rows let the differencing arithmetic resolve this
    quarter. Without it (first quarters need none) the cash flow fields are
    None rather than wrong.
    """
    validate_quarter_end(quarter_end)
    document = _statements_document(package_bytes)
    _validate_document(document, cvm_code, quarter_end)

    rows = _document_rows(document)
    cash_flow_rows = rows[CASH_FLOW_SECTION]
    if previous_package_bytes is not None:
        previous_document = _statements_document(previous_package_bytes)
        _validate_document_company(previous_document, cvm_code)
        cash_flow_rows = cash_flow_rows + _document_rows(
            previous_document,
        )[CASH_FLOW_SECTION]

    return build_quarter_statements(
        rows[INCOME_SECTION],
        cash_flow_rows,
        rows[ASSETS_SECTION],
        rows[LIABILITIES_SECTION],
        cvm_code=cvm_code,
        quarter_end=quarter_end,
    )


def _statements_document(package_bytes: bytes) -> ElementTree.Element:
    """The statements XML inside the package, found by its root element.

    The package also carries registration metadata, a rendered PDF and a
    spreadsheet; file names are not documented, so the root tag is the only
    contract worth relying on.
    """
    try:
        package = zipfile.ZipFile(io.BytesIO(package_bytes))
    except zipfile.BadZipFile as error:
        raise CvmParseError(f"The filing package is not a zip: {error}") from error

    for name in package.namelist():
        if not name.lower().endswith(".xml"):
            continue
        try:
            root = ElementTree.fromstring(package.read(name))
        except ElementTree.ParseError:
            continue
        if root.tag == STATEMENTS_ROOT_TAG:
            return root
    raise CvmParseError("The filing package holds no statements document.")


def _document_text(document: ElementTree.Element, path: str) -> str:
    element = document.find(path)
    if element is None or not (element.text or "").strip():
        raise CvmParseError(f"The statements document is missing {path}.")
    return element.text.strip()


def _document_date(document: ElementTree.Element, path: str) -> date:
    raw = _document_text(document, path)
    try:
        return datetime.strptime(raw, ENET_DATE_FORMAT).date()
    except ValueError as error:
        raise CvmParseError(f"{path} is not a date: {raw!r}") from error


def _validate_document(
    document: ElementTree.Element, cvm_code: str, quarter_end: date,
) -> None:
    _validate_document_company(document, cvm_code)
    reference = _document_date(document, "DadosITR/DataReferencia")
    if reference != quarter_end:
        raise CvmParseError(
            f"The filing reports on {reference}, not {quarter_end}."
        )


def _validate_document_company(
    document: ElementTree.Element, cvm_code: str,
) -> None:
    filed_code = _normalize_cvm_code(
        _document_text(document, "DadosEmpresa/CodigoCvm"),
    )
    wanted = cvm_code.lstrip("0") or "0"
    if filed_code != wanted:
        raise CvmParseError(
            f"The filing belongs to CVM code {filed_code}, not {wanted}."
        )


def _scale_marker(document: ElementTree.Element) -> str:
    code = _document_text(document, "DadosITR/EscalaMoeda")
    marker = SCALE_CODE_TO_CSV_MARKER.get(code)
    if marker is None:
        raise CvmParseError(f"Unknown currency scale code {code!r}.")
    return marker


def _amount(raw: str) -> str:
    """A dotted grid amount as the plain number string VL_CONTA carries."""
    if DOTTED_AMOUNT_PATTERN.fullmatch(raw) is None:
        raise CvmParseError(f"Unreadable amount {raw!r}.")
    return raw.replace(".", "").replace(",", ".")


def _document_rows(document: ElementTree.Element) -> dict[str, list[dict]]:
    """Convert the consolidated statements into open-data CSV vocabulary rows.

    Only ``DfConsolidadas`` is read, mirroring the archive path's use of the
    ``_con`` files alone; a filer without consolidated statements yields an
    empty quarter rather than individual figures no other source reports.
    """
    reference = _document_date(document, "DadosITR/DataReferencia")
    quarter_start = _document_date(document, "DadosITR/DtInicioTrimestreAtual")
    fiscal_year_start = _document_date(
        document, "DadosITR/DtInicioExercicioSocialCurso",
    )
    scale = _scale_marker(document)
    consolidated = document.find("DadosITR/Formulario/DfConsolidadas")

    def section_rows(section_name, builder):
        if consolidated is None:
            return []
        section = consolidated.find(section_name)
        if section is None:
            return []
        rows = []
        for account in section.findall("Conta"):
            rows.extend(builder(account))
        return rows

    def account_row(account, value, start, end):
        return {
            "CD_CONTA": _document_text(account, "CodigoConta"),
            "DS_CONTA": _account_description(account),
            "VL_CONTA": _amount(value),
            "ESCALA_MOEDA": scale,
            "DT_INI_EXERC": start.isoformat(),
            "DT_FIM_EXERC": end.isoformat(),
        }

    def income_rows(account):
        rows = []
        quarter = _column(account, QUARTER_COLUMN)
        if quarter is not None:
            rows.append(account_row(account, quarter, quarter_start, reference))
        year_to_date = _column(account, INCOME_YEAR_TO_DATE_COLUMN)
        if year_to_date is not None:
            rows.append(
                account_row(account, year_to_date, fiscal_year_start, reference),
            )
        return rows

    def cash_flow_rows(account):
        year_to_date = _column(account, CASH_FLOW_YEAR_TO_DATE_COLUMN)
        if year_to_date is None:
            return []
        return [account_row(account, year_to_date, fiscal_year_start, reference)]

    def balance_rows(account):
        snapshot = _column(account, QUARTER_COLUMN)
        if snapshot is None:
            return []
        return [account_row(account, snapshot, reference, reference)]

    return {
        INCOME_SECTION: section_rows(INCOME_SECTION, income_rows),
        CASH_FLOW_SECTION: section_rows(CASH_FLOW_SECTION, cash_flow_rows),
        ASSETS_SECTION: section_rows(ASSETS_SECTION, balance_rows),
        LIABILITIES_SECTION: section_rows(LIABILITIES_SECTION, balance_rows),
    }


def _column(account: ElementTree.Element, column: str) -> str | None:
    element = account.find(column)
    if element is None or not (element.text or "").strip():
        return None
    return element.text.strip()


def _account_description(account: ElementTree.Element) -> str:
    element = account.find("DescricaoConta")
    if element is None or element.text is None:
        return ""
    return element.text.strip()
