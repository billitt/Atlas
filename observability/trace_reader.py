"""Read and format Atlas OpenTelemetry trace files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


def list_traces(directory: str = "data/traces/") -> list[JsonDict]:
    """List trace JSON files with basic metadata, newest first."""
    root = Path(directory)
    if not root.exists():
        return []

    traces: list[JsonDict] = []
    for path in sorted(root.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        spans = payload.get("spans") or []
        trace_ids = {span.get("trace_id") for span in spans if span.get("trace_id")}
        traces.append(
            {
                "path": str(path),
                "filename": path.name,
                "span_count": len(spans),
                "trace_ids": sorted(trace_ids),
                "exported_at": payload.get("exported_at"),
            }
        )
    return traces


def load_trace(filepath: str) -> JsonDict:
    """Load a trace file and build a span tree grouped by trace id."""
    path = Path(filepath)
    payload = json.loads(path.read_text(encoding="utf-8"))
    spans = payload.get("spans") or []
    grouped: dict[str, list[JsonDict]] = {}
    for span in spans:
        trace_id = str(span.get("trace_id", "unknown"))
        grouped.setdefault(trace_id, []).append(span)

    trees: dict[str, list[JsonDict]] = {}
    for trace_id, trace_spans in grouped.items():
        trees[trace_id] = _build_span_tree(trace_spans)

    return {
        "path": str(path),
        "exported_at": payload.get("exported_at"),
        "span_count": len(spans),
        "trace_ids": sorted(grouped.keys()),
        "trees": trees,
        "spans": spans,
    }


def format_trace_tree(trace: JsonDict, *, trace_id: str | None = None) -> str:
    """Render a human-readable indented span tree with timing."""
    trees = trace.get("trees") or {}
    if not trees:
        return "(no spans in trace file)"

    selected_id = trace_id or (trace.get("trace_ids") or [None])[0]
    if selected_id is None or selected_id not in trees:
        selected_id = next(iter(trees.keys()))

    lines = [f"trace_id={selected_id}"]
    for root in trees[selected_id]:
        lines.extend(_format_node(root, depth=0))
    return "\n".join(lines)


def _build_span_tree(spans: list[JsonDict]) -> list[JsonDict]:
    by_id = {span["span_id"]: {**span, "children": []} for span in spans if span.get("span_id")}
    roots: list[JsonDict] = []
    for span in by_id.values():
        parent_id = span.get("parent_span_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(span)
        else:
            roots.append(span)
    _sort_tree(roots)
    return roots


def _sort_tree(nodes: list[JsonDict]) -> None:
    nodes.sort(key=lambda node: node.get("start_time_unix_nano") or 0)
    for node in nodes:
        children = node.get("children") or []
        if children:
            _sort_tree(children)


def _format_node(node: JsonDict, *, depth: int) -> list[str]:
    indent = "  " * depth
    attrs = node.get("attributes") or {}
    attr_bits = []
    for key in (
        "node_name",
        "agent_name",
        "attempt_number",
        "reflection_passed",
        "confidence",
        "tool_name",
        "target_agent",
        "model_name",
        "claims_checked",
        "claims_flagged",
        "overall_confidence",
        "passed",
        "briefing_type",
        "topics_count",
        "rule_id",
        "triggered",
        "severity",
    ):
        if key in attrs:
            attr_bits.append(f"{key}={attrs[key]}")
    attr_text = f" [{', '.join(attr_bits)}]" if attr_bits else ""
    line = (
        f"{indent}- {node.get('name')} "
        f"({node.get('duration_ms', 0)} ms){attr_text}"
    )
    lines = [line]
    for child in node.get("children") or []:
        lines.extend(_format_node(child, depth=depth + 1))
    return lines
