"""Tests for reading the CVM ITR index without downloading the whole archive.

The index (``itr_cia_aberta_<year>.csv``) lists every filing with the date CVM
received it. It is not published as a standalone file — it exists only as the
first entry inside the 12 MB annual archive — so these tests pin the two
mechanics that let it be read cheaply: a conditional HEAD that reports whether
the archive was rebuilt at all, and a ranged read that inflates only the first
zip entry.
"""
import io
import random
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from quotes.cvm import (
    ArchiveState,
    CvmParseError,
    FilingRecord,
    build_itr_index_filename,
    download_itr_index,
    fetch_itr_archive_state,
    parse_itr_index,
)

INDEX_COLUMNS = (
    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC"
)

GERDAU_ROW = (
    "33.611.500/0001-19;2026-06-30;1;GERDAU S.A.;003980;ITR;160123;2026-08-04;"
    "http://www.rad.cvm.gov.br/x"
)
BANCO_DO_BRASIL_ROW = (
    "00.000.000/0001-91;2026-03-31;1;BCO BRASIL S.A.;001023;ITR;157308;2026-05-13;"
    "http://www.rad.cvm.gov.br/y"
)


def build_index_csv(*rows):
    return "\n".join([INDEX_COLUMNS, *rows]).encode("latin-1")


def many_filings(count):
    """Distinct rows, so the fixture compresses like the real index does."""
    return [
        GERDAU_ROW.replace(";160123;", f";{160000 + number};")
        .replace("GERDAU S.A.", f"COMPANHIA {number:05d} S.A.")
        for number in range(count)
    ]


def build_archive(index_bytes, *, index_first=True, filler_size=0):
    """A zip shaped like CVM's: the index first, statement files after it.

    The filler is incompressible so the fixture's proportions match the real
    archive, where the index is a fraction of a percent of the whole.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        entries = [(build_itr_index_filename(2026), index_bytes)]
        if filler_size:
            filler = random.Random(0).randbytes(filler_size)
            entries.append(("itr_cia_aberta_DRE_con_2026.csv", filler))
        if not index_first:
            entries.reverse()
        for name, payload in entries:
            archive.writestr(name, payload)
    return buffer.getvalue()


# --- Index filename ---------------------------------------------------------

def test_index_filename_follows_the_archive_naming():
    assert build_itr_index_filename(2026) == "itr_cia_aberta_2026.csv"


# --- Parsing ----------------------------------------------------------------

def test_parses_a_filing_into_a_record():
    records = parse_itr_index(build_index_csv(GERDAU_ROW))

    assert records == [
        FilingRecord(
            cvm_code="3980",
            company_name="GERDAU S.A.",
            cnpj="33.611.500/0001-19",
            reference_date=date(2026, 6, 30),
            filed_at=date(2026, 8, 4),
            version=1,
            document_id="160123",
        )
    ]


def test_strips_the_zero_padding_from_the_cvm_code():
    """The statement files key on the unpadded code; the index pads to six."""
    [record] = parse_itr_index(build_index_csv(BANCO_DO_BRASIL_ROW))

    assert record.cvm_code == "1023"


def test_decodes_latin_1_company_names():
    row = GERDAU_ROW.replace("GERDAU S.A.", "AMBEV PARTICIPAÇÕES S.A.")
    [record] = parse_itr_index(build_index_csv(row))

    assert record.company_name == "AMBEV PARTICIPAÇÕES S.A."


def test_tolerates_a_filing_with_no_received_date():
    """DT_RECEB is occasionally blank; the row is still a real filing."""
    row = GERDAU_ROW.replace(";2026-08-04;", ";;")
    [record] = parse_itr_index(build_index_csv(row))

    assert record.filed_at is None
    assert record.cvm_code == "3980"


def test_keeps_every_version_of_a_restated_filing():
    """A restatement is its own filing event and has its own received date."""
    restated = GERDAU_ROW.replace(";1;", ";2;").replace(";2026-08-04;", ";2026-08-20;")
    records = parse_itr_index(build_index_csv(GERDAU_ROW, restated))

    assert [(record.version, record.filed_at) for record in records] == [
        (1, date(2026, 8, 4)), (2, date(2026, 8, 20)),
    ]


def test_skips_blank_trailing_lines():
    records = parse_itr_index(build_index_csv(GERDAU_ROW) + b"\n\n")

    assert len(records) == 1


# --- Archive state (the rebuild cadence signal) -----------------------------

def test_archive_state_reports_last_modified_and_etag():
    response = Mock(headers={
        "Last-Modified": "Sun, 09 Aug 2026 10:39:17 GMT",
        "ETag": '"6a7858d5-c53f10"',
    })
    with patch("quotes.cvm.requests.head", return_value=response) as head:
        state = fetch_itr_archive_state(2026)

    assert state == ArchiveState(
        last_modified=datetime(2026, 8, 9, 10, 39, 17, tzinfo=timezone.utc),
        etag='"6a7858d5-c53f10"',
    )
    assert "itr_cia_aberta_2026.zip" in head.call_args.args[0]


def test_archive_state_tolerates_a_missing_last_modified():
    response = Mock(headers={})
    with patch("quotes.cvm.requests.head", return_value=response):
        state = fetch_itr_archive_state(2026)

    assert state.last_modified is None
    assert state.etag == ""


def test_archive_state_raises_when_the_server_errors():
    """A failed HEAD must not read as 'no build time', which would send the
    caller off to download the whole archive during a CVM outage."""
    response = Mock(headers={})
    response.raise_for_status.side_effect = requests.HTTPError("503")

    with patch("quotes.cvm.requests.head", return_value=response):
        with pytest.raises(requests.HTTPError):
            fetch_itr_archive_state(2026)


# --- Ranged index download --------------------------------------------------

def _ranged_response(archive_bytes):
    """Serve only the bytes a Range header asks for, as CVM's nginx does."""
    def get(url, headers=None, timeout=None):
        header_range = (headers or {}).get("Range", "")
        if header_range.startswith("bytes=0-"):
            end = int(header_range.split("-")[1])
            body = archive_bytes[: end + 1]
        else:
            body = archive_bytes
        return Mock(content=body, raise_for_status=Mock())
    return get


def test_downloads_only_the_first_entry_and_inflates_it():
    index = build_index_csv(GERDAU_ROW, BANCO_DO_BRASIL_ROW)
    archive = build_archive(index)

    with patch("quotes.cvm.requests.get", side_effect=_ranged_response(archive)):
        assert download_itr_index(2026) == index


def test_the_ranged_read_is_a_small_fraction_of_the_archive():
    """The whole point: an hourly poll must not pull the whole archive."""
    archive = build_archive(build_index_csv(GERDAU_ROW), filler_size=2_000_000)
    requested = []

    def get(url, headers=None, timeout=None):
        requested.append(headers["Range"])
        end = int(headers["Range"].split("-")[1])
        return Mock(content=archive[: end + 1], raise_for_status=Mock())

    with patch("quotes.cvm.requests.get", side_effect=get):
        download_itr_index(2026)

    [only_request] = requested
    requested_bytes = int(only_request.split("-")[1]) + 1
    assert requested_bytes < len(archive) / 4


def test_widens_the_range_when_the_first_read_truncates_the_entry():
    """A silently truncated inflate would under-report the filing count."""
    index = build_index_csv(*many_filings(4000))
    archive = build_archive(index, filler_size=1_000_000)
    sizes = []

    def get(url, headers=None, timeout=None):
        end = int(headers["Range"].split("-")[1])
        sizes.append(end + 1)
        return Mock(content=archive[: end + 1], raise_for_status=Mock())

    with patch("quotes.cvm.requests.get", side_effect=get), \
         patch("quotes.cvm.INDEX_PREFIX_BYTES", 1024):
        assert download_itr_index(2026) == index

    assert len(sizes) > 1, "expected the reader to widen its range"
    assert sizes == sorted(sizes)


def test_falls_back_to_the_full_archive_when_the_index_is_not_first():
    """Layout is CVM's choice, not a guarantee; never return a wrong file."""
    index = build_index_csv(GERDAU_ROW)
    archive = build_archive(index, index_first=False, filler_size=100_000)

    with patch("quotes.cvm.requests.get", side_effect=_ranged_response(archive)), \
         patch("quotes.cvm.download_itr_archive", return_value=archive) as full:
        assert download_itr_index(2026) == index

    full.assert_called_once_with(2026)


def test_raises_when_neither_the_ranged_read_nor_the_archive_holds_an_index():
    archive = build_archive(b"", index_first=False, filler_size=100_000)
    without_index = io.BytesIO()
    with zipfile.ZipFile(without_index, "w") as stripped:
        stripped.writestr("itr_cia_aberta_DRE_con_2026.csv", b"x")

    with patch("quotes.cvm.requests.get", side_effect=_ranged_response(archive)), \
         patch("quotes.cvm.download_itr_archive", return_value=without_index.getvalue()):
        with pytest.raises(CvmParseError, match="index"):
            download_itr_index(2026)
