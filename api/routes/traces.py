"""OpenTelemetry trace routes."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from api.security import AuthDep
from cli.main import _find_trace_file
from observability.trace_reader import format_trace_tree, list_traces, load_trace

router = APIRouter()

_TRACE_ID_RE = re.compile(r"^[0-9a-f]{16,32}$", re.IGNORECASE)


def _validate_trace_id(trace_id: str) -> str:
    cleaned = trace_id.strip().lower()
    if not _TRACE_ID_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="Invalid trace id")
    return cleaned


@router.get("/traces")
async def traces_list(_auth: AuthDep) -> dict:
    """List recent trace export files."""
    entries = list_traces()
    return {
        "traces": [
            {
                "path": entry.get("path"),
                "filename": entry.get("filename"),
                "span_count": entry.get("span_count"),
                "trace_ids": entry.get("trace_ids"),
                "exported_at": entry.get("exported_at"),
            }
            for entry in entries
        ]
    }


@router.get("/traces/{trace_id}")
async def trace_detail(trace_id: str, _auth: AuthDep) -> dict:
    """Load one trace by id when it maps to a real export file."""
    cleaned = _validate_trace_id(trace_id)
    path = _find_trace_file(cleaned)
    if path is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    trace = load_trace(path)
    if cleaned not in (trace.get("trace_ids") or []):
        raise HTTPException(status_code=404, detail="Trace not found")

    tree_text = format_trace_tree(trace, trace_id=cleaned)
    return {
        "trace_id": cleaned,
        "path": trace.get("path"),
        "exported_at": trace.get("exported_at"),
        "span_count": trace.get("span_count"),
        "tree": tree_text,
        "trees": trace.get("trees", {}).get(cleaned, []),
    }
