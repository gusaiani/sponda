"""JSON log formatter.

Emits one JSON object per log record. Intentionally hand-rolled (no
python-json-logger dep) so it stays small and predictable.
"""
from __future__ import annotations

import json
import logging
import time

from config.middleware.request_id import current_request_id


class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = current_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
