"""Pure formatting helpers for Atlas scheduled briefings."""

from __future__ import annotations

from typing import Any

JsonDict = dict[str, Any]


def format_daily_briefing(briefing: JsonDict) -> str:
    """Render a structured briefing without LLM calls or data fetching."""
    lines = [
        f"Atlas {str(briefing.get('briefing_type', 'daily')).title()} Briefing",
        f"Timestamp: {briefing.get('timestamp')}",
        f"Overall risk: [{briefing.get('overall_risk_level', 'LOW')}]",
        "",
        "What changed:",
        str(briefing.get("delta_from_last") or "No prior briefing delta available."),
        "",
        "Sections:",
    ]
    for section in briefing.get("sections", []):
        guardian = section.get("guardian_verdict", {}) or {}
        flags = guardian.get("flags", []) or []
        sources = section.get("sources", []) or []
        lines.extend(
            [
                "",
                f"## {section.get('topic', 'Untitled topic')}",
                f"Confidence: [{section.get('confidence', 'LOW')}]",
                f"Guardian: {guardian.get('overall_confidence', 'LOW')} "
                f"({'passed' if guardian.get('passed') else 'flagged'})",
                f"Sources: {len(sources)}",
                "",
                str(section.get("analysis", "")).strip(),
            ]
        )
        if flags:
            lines.append("")
            lines.append("Guardian flags:")
            lines.extend(f"- {flag}" for flag in flags)
        if section.get("delta_from_last"):
            lines.append("")
            lines.append(f"Delta: {section['delta_from_last']}")
    return "\n".join(lines).strip()


def format_summary_line(briefing: JsonDict) -> str:
    """Return a one-line notification summary."""
    topics = briefing.get("topics") or [section.get("topic") for section in briefing.get("sections", [])]
    topic_text = ", ".join(str(topic) for topic in topics if topic)
    sections = briefing.get("sections", [])
    flagged = sum(1 for section in sections if (section.get("guardian_verdict") or {}).get("flags"))
    return (
        f"Atlas {briefing.get('briefing_type', 'daily')} briefing: "
        f"{len(sections)} sections, risk={briefing.get('overall_risk_level', 'LOW')}, "
        f"flagged={flagged}, topics={topic_text}"
    )
