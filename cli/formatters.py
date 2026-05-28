"""Terminal output formatting for the Atlas CLI."""

from __future__ import annotations

from typing import Any

import typer

JsonDict = dict[str, Any]


def _confidence_style(confidence: str) -> str:
    level = str(confidence or "LOW").upper()
    if level == "HIGH":
        return typer.style(level, fg=typer.colors.GREEN, bold=True)
    if level == "MEDIUM":
        return typer.style(level, fg=typer.colors.YELLOW, bold=True)
    return typer.style(level, fg=typer.colors.RED, bold=True)


def _severity_style(severity: str) -> str:
    level = str(severity or "LOW").upper()
    if level == "HIGH":
        return typer.style(level, fg=typer.colors.RED, bold=True)
    if level == "MEDIUM":
        return typer.style(level, fg=typer.colors.YELLOW, bold=True)
    return typer.style(level, fg=typer.colors.GREEN, bold=True)


def _ok(value: bool) -> str:
    if value:
        return typer.style("OK", fg=typer.colors.GREEN, bold=True)
    return typer.style("DOWN", fg=typer.colors.RED, bold=True)


def format_query_result(briefing: JsonDict, *, trace_id: str | None = None) -> str:
    """Render a synthesis query result with confidence badges and sources."""
    lines = [
        typer.style("Atlas Query Result", bold=True),
        f"Overall confidence: {_confidence_style(str(briefing.get('overall_confidence', 'LOW')))}",
    ]
    if trace_id:
        lines.append(f"trace_id: {typer.style(trace_id, fg=typer.colors.CYAN)}")

    guardian = briefing.get("guardian_verdict") or {}
    passed = guardian.get("passed", False)
    pass_text = (
        typer.style("PASSED", fg=typer.colors.GREEN)
        if passed
        else typer.style("FLAGGED", fg=typer.colors.RED)
    )
    lines.append(
        f"Guardian: {_confidence_style(str(guardian.get('overall_confidence', 'LOW')))} ({pass_text})"
    )

    lines.extend(
        ["", typer.style("Analysis", bold=True), str(briefing.get("combined_analysis", "")).strip()]
    )

    per_agent = briefing.get("per_agent_sources") or {}
    if per_agent:
        lines.extend(["", typer.style("Sources by agent", bold=True)])
        if isinstance(per_agent, dict):
            for agent, sources in per_agent.items():
                count = len(sources) if isinstance(sources, list) else 0
                lines.append(f"  - {agent}: {count} source(s)")
        else:
            lines.append(f"  {per_agent}")

    flags = guardian.get("flags") or []
    if flags:
        lines.extend(["", typer.style("Guardian flags", fg=typer.colors.YELLOW, bold=True)])
        lines.extend(f"  - {flag}" for flag in flags)

    return "\n".join(lines)


def format_briefing_output(briefing: JsonDict, *, trace_id: str | None = None) -> str:
    """Render a scheduled briefing with colored risk and confidence badges."""
    lines = [
        typer.style(
            f"Atlas {str(briefing.get('briefing_type', 'daily')).title()} Briefing", bold=True
        ),
        f"Timestamp: {briefing.get('timestamp')}",
        f"Overall risk: {_confidence_style(str(briefing.get('overall_risk_level', 'LOW')))}",
    ]
    if trace_id:
        lines.append(f"trace_id: {typer.style(trace_id, fg=typer.colors.CYAN)}")
    lines.extend(
        [
            "",
            typer.style("What changed", bold=True),
            str(briefing.get("delta_from_last") or "No prior briefing delta available."),
            "",
            typer.style("Sections", bold=True),
        ]
    )
    for section in briefing.get("sections", []):
        guardian = section.get("guardian_verdict") or {}
        flags = guardian.get("flags") or []
        sources = section.get("sources") or []
        passed = guardian.get("passed", False)
        pass_text = (
            typer.style("passed", fg=typer.colors.GREEN)
            if passed
            else typer.style("flagged", fg=typer.colors.RED)
        )
        lines.extend(
            [
                "",
                typer.style(f"## {section.get('topic', 'Untitled topic')}", bold=True),
                f"Confidence: {_confidence_style(str(section.get('confidence', 'LOW')))}",
                f"Guardian: {_confidence_style(str(guardian.get('overall_confidence', 'LOW')))} ({pass_text})",
                f"Sources: {len(sources)}",
                "",
                str(section.get("analysis", "")).strip(),
            ]
        )
        if flags:
            lines.append("")
            lines.append(typer.style("Guardian flags:", fg=typer.colors.YELLOW))
            lines.extend(f"  - {flag}" for flag in flags)
    return "\n".join(lines).strip()


def format_alert(alert: JsonDict) -> str:
    """Render a triggered alert with severity-colored header."""
    severity = str(alert.get("severity", "LOW"))
    header = typer.style(
        f"ATLAS ALERT [{severity}] {alert.get('rule_name')}",
        fg=typer.colors.RED if severity == "HIGH" else typer.colors.YELLOW,
        bold=True,
    )
    return "\n".join(
        [
            "",
            "=" * 72,
            header,
            "=" * 72,
            f"Triggered: {alert.get('triggered_at')}",
            f"Rule ID: {alert.get('rule_id')}",
            f"Severity: {_severity_style(severity)}",
            "",
            typer.style("Summary", bold=True),
            str(alert.get("summary", "")),
            "",
            typer.style("Evidence", bold=True),
            str(alert.get("evidence", "")),
            "",
            typer.style("Context", bold=True),
            str(alert.get("context", "")),
        ]
    )


def format_status(status: JsonDict) -> str:
    """Render a system health dashboard."""
    lines = [typer.style("Atlas System Status", bold=True), ""]

    ollama = status.get("ollama") or {}
    lines.append(typer.style("Ollama", bold=True))
    lines.append(f"  Reachable: {_ok(bool(ollama.get('reachable')))}")
    lines.append(f"  Model configured: {ollama.get('model', 'unknown')}")
    lines.append(f"  Model loaded: {_ok(bool(ollama.get('model_loaded')))}")

    lines.append("")
    lines.append(typer.style("MCP Servers", bold=True))
    for server in status.get("mcp_servers") or []:
        lines.append(
            f"  {server.get('name')} ({server.get('url')}): {_ok(bool(server.get('reachable')))}"
        )

    memory = status.get("memory") or {}
    lines.append("")
    lines.append(typer.style("Memory", bold=True))
    lines.append(f"  Semantic documents: {memory.get('semantic_docs', 0)}")
    lines.append(f"  Episodic briefings: {memory.get('episodic_briefings', 0)}")
    lines.append(f"  Episodic alerts: {memory.get('episodic_alerts', 0)}")

    last_briefing = status.get("last_briefing")
    lines.append("")
    lines.append(typer.style("Last Briefing", bold=True))
    if last_briefing:
        lines.append(f"  Timestamp: {last_briefing.get('timestamp')}")
        lines.append(f"  Query: {last_briefing.get('query')}")
        lines.append(
            f"  Confidence: {_confidence_style(str(last_briefing.get('confidence', 'LOW')))}"
        )
    else:
        lines.append("  (none)")

    last_alert = status.get("last_alert")
    lines.append("")
    lines.append(typer.style("Last Alert", bold=True))
    if last_alert:
        lines.append(f"  Timestamp: {last_alert.get('timestamp')}")
        lines.append(f"  Rule: {last_alert.get('rule_name')}")
        lines.append(f"  Severity: {_severity_style(str(last_alert.get('severity', 'LOW')))}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_trace_tree(tree: str) -> str:
    """Highlight trace tree headers for terminal display."""
    lines = []
    for line in tree.splitlines():
        if line.startswith("trace_id="):
            trace_id = line.split("=", 1)[1]
            lines.append(
                f"{typer.style('trace_id', bold=True)}={typer.style(trace_id, fg=typer.colors.CYAN)}"
            )
        elif line.strip().startswith("- "):
            name_part = line.strip()[2:]
            if " ms)" in name_part:
                name, rest = name_part.split(" (", 1)
                lines.append(f"  - {typer.style(name, bold=True)} ({rest}")
            else:
                lines.append(f"  - {typer.style(name_part, bold=True)}")
        else:
            lines.append(line)
    return "\n".join(lines)


def format_history_row(record: JsonDict) -> str:
    """Render one episodic briefing history row."""
    confidence = _confidence_style(str(record.get("confidence", "LOW")))
    duration = record.get("duration_seconds")
    duration_text = f"{duration}s" if duration is not None else "n/a"
    trace = record.get("trace_id")
    trace_text = f" trace={trace}" if trace else ""
    return (
        f"{record.get('timestamp')} | {confidence} | {duration_text} | "
        f"{record.get('query', '')}{trace_text}"
    )
