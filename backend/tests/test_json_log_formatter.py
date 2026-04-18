"""Tests for the JSON log formatter.

The formatter must emit a single-line JSON object per record with at least:
  timestamp, level, logger, message. When a request is in flight, it also
  includes request_id.
"""
import json
import logging

from config.logging_formatter import JSONLogFormatter
from config.middleware.request_id import REQUEST_ID_CONTEXT


def _make_record(message="hello", level=logging.INFO, logger_name="test"):
    return logging.LogRecord(
        name=logger_name,
        level=level,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )


class TestJSONLogFormatter:
    def test_emits_single_line_json(self):
        record = _make_record()
        output = JSONLogFormatter().format(record)
        assert "\n" not in output
        payload = json.loads(output)
        assert payload["message"] == "hello"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "test"
        assert "timestamp" in payload

    def test_includes_request_id_when_in_context(self):
        token = REQUEST_ID_CONTEXT.set("req-xyz")
        try:
            payload = json.loads(JSONLogFormatter().format(_make_record()))
            assert payload["request_id"] == "req-xyz"
        finally:
            REQUEST_ID_CONTEXT.reset(token)

    def test_omits_request_id_when_not_in_context(self):
        payload = json.loads(JSONLogFormatter().format(_make_record()))
        assert "request_id" not in payload

    def test_includes_exc_info_when_present(self):
        try:
            raise ValueError("kaboom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=20,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        payload = json.loads(JSONLogFormatter().format(record))
        assert "kaboom" in payload["exception"]
        assert "ValueError" in payload["exception"]
