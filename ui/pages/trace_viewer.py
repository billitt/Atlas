"""Execution trace explorer page."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from observability.trace_reader import format_trace_tree, list_traces, load_trace
from ui.components import render_span_tree
from ui.runtime import find_run_log_by_trace_id


def _query_from_trace_path(path: str) -> str:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    for span in payload.get("spans") or []:
        query = (span.get("attributes") or {}).get("query")
        if query:
            return str(query)[:120]
    return ""


def render() -> None:
    st.header("Trace Viewer")
    st.caption("Explore OpenTelemetry execution traces from data/traces/")

    entries = list_traces()
    if not entries:
        st.info(
            "No traces found. Run a query with OTEL_EXPORT_TO=file or use the tracing demo first."
        )
        st.code(
            "$env:OTEL_EXPORT_TO = 'file'\natlas query \"Your question here\"",
            language="powershell",
        )
        return

    labels = []
    for entry in entries:
        query = _query_from_trace_path(str(entry["path"]))
        trace_ids = ", ".join(entry.get("trace_ids") or []) or "unknown"
        labels.append(
            f"{entry.get('exported_at') or entry.get('filename')} | {trace_ids} | {query or '(no query)'}"
        )

    selected = st.selectbox("Recent traces", range(len(entries)), format_func=lambda i: labels[i])
    entry = entries[selected]
    trace_ids = entry.get("trace_ids") or []

    prefill = st.session_state.pop("trace_viewer_id", "")
    trace_id_input = st.text_input(
        "Trace ID (optional override)",
        value=prefill or (trace_ids[0] if trace_ids else ""),
        help="32-char hex trace id",
    )
    trace_id = trace_id_input.strip() or (trace_ids[0] if trace_ids else "")

    if not trace_id:
        st.warning("No trace id available for this file.")
        return

    trace = load_trace(str(entry["path"]))
    tree_text = format_trace_tree(trace, trace_id=trace_id)
    st.code(tree_text, language="text")

    st.subheader("Span tree")
    trees = trace.get("trees") or {}
    nodes = trees.get(trace_id) or []
    if nodes:
        render_span_tree(nodes)
    else:
        st.caption("No span tree for this trace id.")

    run_log = find_run_log_by_trace_id(trace_id)
    if run_log:
        st.success(f"Linked run log: `{run_log}`")
        with st.expander("Run log JSON"):
            st.json(json.loads(run_log.read_text(encoding="utf-8")))
    else:
        st.caption("No matching run log in runs/ for this trace_id.")
