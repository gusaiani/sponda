"""JSON-safety helpers shared by every payload built from model fields.

Django ``DecimalField`` values arrive as ``Decimal``, which ``json.dumps``
refuses. Both the assistant's tool executors and the DB-only company
payloads behind the markdown pages have to convert before serialising, so
the conversion lives here rather than in either of them.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def json_safe(value: Any) -> Any:
    """Recursively convert Decimal to float so a structure is json.dumps-able.

    Tool executors source values from Django DecimalFields; both the OpenAI
    SDK and the SSE frame writer call json.dumps on tool results, which
    raises on a bare Decimal without this conversion.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value
