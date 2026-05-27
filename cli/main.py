"""Atlas Typer CLI — user-facing command layer over existing pipelines."""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

import httpx
import typer
from sqlmodel import Session, select

from agents.guardian.agent import GuardianAgent
from agents.market.agent import DEFAULT_MCP_URL
from agents.research.agent import DEFAULT_EDGAR_MCP_URL
from agents.synthesis.agent import SynthesisAgent
from cli.formatters import (
    format_alert,
    format_briefing_output,
    format_history_row,
    format_query_result,
    format_status,
    format_trace_tree,
)
from examples._demo_infra import (
    DEFAULT_AGENT_CARD_URLS,
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from memory.episodic import AlertRecord, BriefingRecord, EpisodicMemory
from memory.semantic import SemanticMemory
from observability.run_logger import save_run
from observability.trace_reader import format_trace_tree as render_trace_tree
from observability.trace_reader import list_traces, load_trace
from observability.tracing import get_current_trace_id, init_tracing, shutdown_tracing
from orchestration.graph import build_synthesis_graph, run_synthesis_graph
from protocols.a2a.discovery import load_cards
from protocols.mcp.client import McpClient
from services.alert_defaults import default_alert_rules
from services.alerts import AlertEngine, AlertResult
from services.alert_watch import AlertWatcher
from services.briefing import BriefingEngine
from services.briefing_templates import format_summary_line
from services.llm import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, list_models

JsonDict = dict[str, Any]

app = typer.Typer(
    name="atlas",
    help="Atlas — local-first global intelligence platform.",
    no_args_is_help=True,
)
alerts_app = typer.Typer(help="Real-time alert checks and watch loops.")
traces_app = typer.Typer(help="OpenTelemetry trace inspection.")
app.add_typer(alerts_app, name="alerts")
app.add_typer(traces_app, name="traces")


class _CliAlertWatcher(AlertWatcher):
    """Alert watcher that prints through CLI formatters."""

    def _on_alert(self, alert_result: AlertResult) -> None:
        typer.echo(format_alert(dict(alert_result)))


def _maybe_init_tracing() -> None:
    import os

    if os.getenv("OTEL_EXPORT_TO"):
        init_tracing()


@contextmanager
def agent_runtime() -> Iterator[list[dict[str, Any]]]:
    """Start MCP check, background A2A servers, and load agent cards."""

    async def _boot() -> list[dict[str, Any]]:
        await start_mcp_check()
        await wait_for_agent_cards(DEFAULT_AGENT_CARD_URLS)
        registry = load_cards("agents")
        return [
            card
            for card in registry.discover_all()
            if "guardian" not in str(card.get("name", "")).lower()
        ]

    servers = start_agent_servers()
    try:
        agent_cards = asyncio.run(_boot())
        yield agent_cards
    finally:
        for server in servers:
            server.shutdown()


def _build_synthesis_stack(agent_cards: list[dict[str, Any]]) -> tuple[SynthesisAgent, EpisodicMemory]:
    episodic_memory = EpisodicMemory()
    synthesis_agent = SynthesisAgent(agent_cards, episodic_memory=episodic_memory)
    return synthesis_agent, episodic_memory


def _collect_status() -> JsonDict:
    ollama_reachable = False
    model_loaded = False
    try:
        models = list_models()
        ollama_reachable = True
        model_loaded = any(OLLAMA_CHAT_MODEL.split(":")[0] in m for m in models) or OLLAMA_CHAT_MODEL in models
    except Exception:
        models = []

    mcp_servers = []
    for name, url in (
        ("mcp-market-data", DEFAULT_MCP_URL),
        ("mcp-edgar", DEFAULT_EDGAR_MCP_URL),
    ):
        reachable = False
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{url.rstrip('/')}/health")
                reachable = response.status_code == 200
        except httpx.HTTPError:
            pass
        mcp_servers.append({"name": name, "url": url, "reachable": reachable})

    semantic = SemanticMemory()
    episodic = EpisodicMemory()
    try:
        semantic_docs = semantic.count()
    except Exception:
        semantic_docs = 0

    with Session(episodic.engine) as session:
        last_briefing = session.exec(
            select(BriefingRecord).order_by(BriefingRecord.timestamp.desc()).limit(1)
        ).first()
        last_alert = session.exec(
            select(AlertRecord).order_by(AlertRecord.timestamp.desc()).limit(1)
        ).first()
        alert_count = len(list(session.exec(select(AlertRecord.id))))

    return {
        "ollama": {
            "reachable": ollama_reachable,
            "model": OLLAMA_CHAT_MODEL,
            "model_loaded": model_loaded,
            "base_url": OLLAMA_BASE_URL,
            "models": models,
        },
        "mcp_servers": mcp_servers,
        "memory": {
            "semantic_docs": semantic_docs,
            "episodic_briefings": episodic.briefing_count(),
            "episodic_alerts": alert_count,
        },
        "last_briefing": (
            {
                "timestamp": last_briefing.timestamp.isoformat(timespec="seconds"),
                "query": last_briefing.query,
                "confidence": last_briefing.confidence,
                "trace_id": last_briefing.trace_id,
            }
            if last_briefing
            else None
        ),
        "last_alert": (
            {
                "timestamp": last_alert.timestamp.isoformat(timespec="seconds"),
                "rule_name": last_alert.rule_name,
                "severity": last_alert.severity,
            }
            if last_alert
            else None
        ),
    }


def _trace_query_from_file(path: str) -> str | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for span in payload.get("spans") or []:
        attrs = span.get("attributes") or {}
        if attrs.get("query"):
            return str(attrs["query"])[:120]
    return None


def _find_trace_file(trace_id: str) -> str | None:
    for entry in list_traces():
        if trace_id in (entry.get("trace_ids") or []):
            return str(entry["path"])
    root = Path("data/traces")
    if root.exists():
        for path in sorted(root.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for span in payload.get("spans") or []:
                if span.get("trace_id") == trace_id:
                    return str(path)
    return None


def _build_alert_engine() -> AlertEngine:
    episodic_memory = EpisodicMemory()
    engine = AlertEngine(
        synthesis_agent=None,
        episodic_memory=episodic_memory,
        guardian=GuardianAgent(),
        mcp_client={
            "market": McpClient(DEFAULT_MCP_URL),
            "edgar": McpClient(DEFAULT_EDGAR_MCP_URL),
        },
    )
    for rule in default_alert_rules():
        engine.add_rule(rule)
    return engine


@app.command("query")
def query_command(
    text: str = typer.Argument(..., help="Natural-language intelligence query."),
) -> None:
    """Run the full synthesis pipeline and print a formatted briefing."""
    _maybe_init_tracing()
    typer.echo(f"Running synthesis query: {text}")
    typer.echo("Starting specialist A2A servers...")

    async def _run() -> None:
        started_at = datetime.now().isoformat(timespec="seconds")
        start_time = perf_counter()
        with agent_runtime() as agent_cards:
            synthesis_agent, episodic_memory = _build_synthesis_stack(agent_cards)
            app_graph = build_synthesis_graph(synthesis_agent, guardian=GuardianAgent())
            final_state = await run_synthesis_graph(
                app_graph,
                {
                    "query": text,
                    "messages": [("user", text)],
                    "agent_cards": agent_cards,
                    "agent_results": [],
                    "sources": [],
                    "guardian_retries": 0,
                },
            )
        briefing = final_state["briefing"]
        duration_seconds = round(perf_counter() - start_time, 3)
        trace_id = get_current_trace_id()
        guardian_verdict = briefing.get("guardian_verdict", {})

        run_data = {
            "timestamp": started_at,
            "query": text,
            "execution_plan": briefing["execution_plan"],
            "agent_results": briefing["agent_results"],
            "sources": briefing["per_agent_sources"],
            "confidence": briefing["overall_confidence"],
            "final_briefing": briefing["combined_analysis"],
            "guardian_verdict": guardian_verdict,
            "duration_seconds": duration_seconds,
            "trace_id": trace_id,
        }
        save_run(run_data)
        episodic_memory.log_briefing(run_data)

        typer.echo("")
        typer.echo(format_query_result(briefing, trace_id=trace_id))
        if trace_id:
            typer.echo(f"\nDrill down: atlas traces show {trace_id}")

    try:
        asyncio.run(_run())
    finally:
        shutdown_tracing()


@app.command("briefing")
def briefing_command(
    briefing_type: str = typer.Option("daily", "--type", help="Briefing type: daily, weekly, or custom."),
    topics: str | None = typer.Option(None, "--topics", help="Comma-separated watchlist override."),
) -> None:
    """Generate a scheduled-style briefing over the default or custom watchlist."""
    _maybe_init_tracing()
    selected_topics = [part.strip() for part in topics.split(",") if part.strip()] if topics else None
    typer.echo(f"Generating {briefing_type} briefing...")
    typer.echo("Starting specialist A2A servers...")

    async def _run() -> None:
        with agent_runtime() as agent_cards:
            synthesis_agent, episodic_memory = _build_synthesis_stack(agent_cards)
            engine = BriefingEngine(
                synthesis_agent,
                episodic_memory=episodic_memory,
                guardian=GuardianAgent(),
                briefing_type=briefing_type,
            )
            result = await engine.generate_briefing(selected_topics)

        trace_id = get_current_trace_id() or result.get("trace_id")
        typer.echo("")
        typer.echo(format_briefing_output(result, trace_id=trace_id))
        typer.echo("")
        typer.echo(format_summary_line(result))

    try:
        asyncio.run(_run())
    finally:
        shutdown_tracing()


@app.command("status")
def status_command() -> None:
    """Show Ollama, MCP, memory, and recent activity health."""
    typer.echo(format_status(_collect_status()))


@app.command("history")
def history_command(
    limit: int = typer.Option(10, "--limit", min=1, help="Number of recent briefings to show."),
) -> None:
    """List recent briefings from episodic memory."""
    episodic = EpisodicMemory()
    records = episodic.query_briefings("", limit=limit)
    if not records:
        typer.echo("No briefing history found.")
        raise typer.Exit(0)

    typer.echo(typer.style(f"Recent briefings (limit={limit})", bold=True))
    for record in records:
        typer.echo(
            format_history_row(
                {
                    "timestamp": record.timestamp.isoformat(timespec="seconds"),
                    "query": record.query,
                    "confidence": record.confidence,
                    "duration_seconds": record.duration_seconds,
                    "trace_id": record.trace_id,
                }
            )
        )


@alerts_app.command("check")
def alerts_check_command() -> None:
    """Evaluate all default alert rules once."""

    async def _run() -> None:
        engine = _build_alert_engine()
        triggered = await engine.check_all_rules()
        if not triggered:
            typer.echo("No alerts triggered.")
            return
        for alert in triggered:
            typer.echo(format_alert(dict(alert)))

    asyncio.run(_run())


@alerts_app.command("watch")
def alerts_watch_command(
    interval: int = typer.Option(300, "--interval", min=10, help="Seconds between checks."),
) -> None:
    """Run a continuous alert watch loop until Ctrl+C."""

    async def _run() -> None:
        engine = _build_alert_engine()
        watcher = _CliAlertWatcher(engine, check_interval_seconds=interval)
        typer.echo(f"Watching alerts every {interval}s (Ctrl+C to stop)...")
        try:
            await watcher.start()
        except KeyboardInterrupt:
            watcher.stop()
            typer.echo("\nAlert watch stopped.")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        typer.echo("\nAlert watch stopped.")


@alerts_app.command("rules")
def alerts_rules_command() -> None:
    """List registered default alert rules."""
    typer.echo(typer.style("Alert rules", bold=True))
    for rule in default_alert_rules():
        typer.echo(
            f"  - {rule.id}: {rule.name} "
            f"[{typer.style(rule.severity, fg=typer.colors.RED if rule.severity == 'HIGH' else typer.colors.YELLOW)}] "
            f"cooldown={rule.cooldown_seconds}s"
        )
        typer.echo(f"    {rule.description}")


@traces_app.command("list")
def traces_list_command() -> None:
    """List recent OpenTelemetry trace files."""
    entries = list_traces()
    if not entries:
        typer.echo("No trace files found in data/traces/.")
        raise typer.Exit(0)

    typer.echo(typer.style("Recent traces", bold=True))
    for entry in entries:
        query = _trace_query_from_file(str(entry["path"])) or "(query not captured)"
        trace_ids = ", ".join(entry.get("trace_ids") or []) or "unknown"
        typer.echo(
            f"  {entry.get('exported_at') or entry.get('filename')} | "
            f"spans={entry.get('span_count', 0)} | trace_id={trace_ids} | {query}"
        )


@traces_app.command("show")
def traces_show_command(
    trace_id: str = typer.Argument(..., help="32-char hex trace id from a run log or traces list."),
) -> None:
    """Print a formatted execution trace tree."""
    path = _find_trace_file(trace_id)
    if path is None:
        typer.echo(f"Trace not found: {trace_id}", err=True)
        raise typer.Exit(1)

    trace = load_trace(path)
    tree = render_trace_tree(trace, trace_id=trace_id)
    typer.echo(format_trace_tree(tree))
    typer.echo(f"\nSource file: {path}")


if __name__ == "__main__":
    app()
