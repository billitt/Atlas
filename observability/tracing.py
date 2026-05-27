"""OpenTelemetry tracing initialization and helpers for Atlas."""

from __future__ import annotations

import functools
import inspect
import os
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Tracer

from observability.exporters import (
    create_console_exporter,
    create_file_exporter,
    create_jaeger_exporter,
    get_active_trace_file,
)

_provider: TracerProvider | None = None
F = TypeVar("F", bound=Callable[..., Any])


def init_tracing(
    service_name: str | None = None,
    export_to: str | None = None,
) -> TracerProvider:
    """Initialize Atlas OpenTelemetry tracing.

    Supported exporters via `export_to` or `OTEL_EXPORT_TO`:
    - ``console`` — print spans to stdout (default)
    - ``file`` — write JSON spans to ``data/traces/``
    - ``jaeger`` — OTLP HTTP export when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set
    """
    global _provider
    if _provider is not None:
        return _provider

    resolved_service = service_name or os.getenv("OTEL_SERVICE_NAME", "atlas")
    resolved_export = (export_to or os.getenv("OTEL_EXPORT_TO", "console")).lower().strip()

    resource = Resource.create({"service.name": resolved_service})
    provider = TracerProvider(resource=resource)

    processor: SimpleSpanProcessor
    if resolved_export == "file":
        processor = create_file_exporter()
    elif resolved_export == "jaeger":
        processor = create_jaeger_exporter()
    elif resolved_export == "console":
        processor = create_console_exporter()
    else:
        raise ValueError(f"unsupported OTEL export target: {resolved_export!r}")

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def get_tracer(name: str) -> Tracer:
    """Return a named OpenTelemetry tracer."""
    return trace.get_tracer(name)


def get_current_trace_id() -> str | None:
    """Return the hex trace id of the current span, if tracing is active."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


def get_current_span_id() -> str | None:
    """Return the hex span id of the current span, if tracing is active."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.span_id, "016x")


def shutdown_tracing() -> None:
    """Flush and shut down the active tracer provider."""
    global _provider
    if _provider is None:
        return
    _provider.force_flush()
    _provider.shutdown()
    _provider = None


def traced(name: str | None = None) -> Callable[[F], F]:
    """Decorator that wraps sync or async functions in an OpenTelemetry span."""

    def decorator(fn: F) -> F:
        span_name = name or fn.__qualname__

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer(fn.__module__)
                with tracer.start_as_current_span(span_name):
                    return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(fn.__module__)
            with tracer.start_as_current_span(span_name):
                return fn(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "get_active_trace_file",
    "get_current_span_id",
    "get_current_trace_id",
    "get_tracer",
    "init_tracing",
    "shutdown_tracing",
    "traced",
]
