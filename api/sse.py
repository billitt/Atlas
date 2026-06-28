"""Server-Sent Events helpers for the query stream."""

from __future__ import annotations

import json
from typing import Any

JsonDict = dict[str, Any]


def format_sse(event: str, data: JsonDict) -> str:
    """Format one SSE message (event + JSON data)."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"
