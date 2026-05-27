"""OpenTelemetry span exporter configuration for Atlas."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

TRACES_DIR = Path("data/traces")
_active_trace_file: Path | None = None


def get_active_trace_file() -> Path | None:
    """Return the path of the current file-based trace export, if any."""
    return _active_trace_file


def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    parent = span.parent
    start_ns = span.start_time or 0
    end_ns = span.end_time or start_ns
    duration_ms = round((end_ns - start_ns) / 1_000_000, 3)
    attributes = dict(span.attributes or {})
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent and parent.span_id else None,
        "name": span.name,
        "kind": span.kind.name if span.kind else "INTERNAL",
        "start_time_unix_nano": start_ns,
        "end_time_unix_nano": end_ns,
        "duration_ms": duration_ms,
        "status": span.status.status_code.name if span.status else "UNSET",
        "attributes": attributes,
    }


class FileSpanExporter(SpanExporter):
    """Append exported spans to a JSON trace file under `data/traces/`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._spans: list[dict[str, Any]] = []

    def export(self, spans: tuple[ReadableSpan, ...]) -> SpanExportResult:
        for span in spans:
            self._spans.append(_span_to_dict(span))
        payload = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "span_count": len(self._spans),
            "spans": self._spans,
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def create_console_exporter() -> SimpleSpanProcessor:
    """Return a processor that prints spans to stdout."""
    return SimpleSpanProcessor(ConsoleSpanExporter())


def create_file_exporter(path: Path | None = None) -> SimpleSpanProcessor:
    """Return a processor that writes JSON spans to `data/traces/YYYYMMDD_HHMMSS.json`."""
    global _active_trace_file
    if path is None:
        path = TRACES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    _active_trace_file = path
    return SimpleSpanProcessor(FileSpanExporter(path))


def create_jaeger_exporter() -> SimpleSpanProcessor:
    """Return a processor backed by OTLP HTTP export (Jaeger-compatible)."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Jaeger export requires OTEL_EXPORTER_OTLP_ENDPOINT "
            "(e.g. http://localhost:4318/v1/traces)"
        )
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError as exc:
        raise RuntimeError(
            "Install opentelemetry-exporter-otlp-proto-http for Jaeger export"
        ) from exc
    return SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
