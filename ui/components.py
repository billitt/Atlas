"""Reusable Streamlit widgets for the Atlas dashboard."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from ui.styles import CONFIDENCE_COLORS, PALETTE, SEVERITY_COLORS

JsonDict = dict[str, Any]


def _pill(label: str, color: str, *, text_color: str = "#0b0f14") -> str:
    safe = html.escape(label.upper())
    return (
        f'<span class="atlas-pill" style="background:{color};color:{text_color};">{safe}</span>'
    )


def confidence_badge(level: str) -> None:
    """Render a colored confidence pill."""
    key = str(level or "LOW").upper()
    st.markdown(_pill(key, CONFIDENCE_COLORS.get(key, CONFIDENCE_COLORS["LOW"])), unsafe_allow_html=True)


def guardian_badge(passed: bool) -> None:
    """Render Guardian pass/fail pill."""
    if passed:
        st.markdown(
            _pill("✓ Passed", PALETTE["success"], text_color="#052e16"),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            _pill("⚑ Flagged", PALETTE["danger"], text_color="#450a0a"),
            unsafe_allow_html=True,
        )


def severity_badge(severity: str) -> None:
    """Render a colored severity pill."""
    key = str(severity or "LOW").upper()
    st.markdown(_pill(key, SEVERITY_COLORS.get(key, SEVERITY_COLORS["LOW"])), unsafe_allow_html=True)


def metric_card(label: str, value: str, *, status: str | None = None) -> None:
    """Styled metric card for status grids."""
    dot_color = PALETTE["text_muted"]
    if status == "ok":
        dot_color = PALETTE["success"]
    elif status == "warn":
        dot_color = PALETTE["warning"]
    elif status == "error":
        dot_color = PALETTE["danger"]
    status_html = (
        f'<span class="atlas-status-dot" style="background:{dot_color};"></span>'
        if status
        else ""
    )
    st.markdown(
        f"""
        <div class="atlas-card">
          <div class="atlas-metric-label">{html.escape(label)}</div>
          <div class="atlas-metric-value">{status_html}{html.escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def agent_status_card(name: str, port: str, reachable: bool, skills: list[str]) -> None:
    """Render a formatted agent status card with skill tags."""
    dot = PALETTE["success"] if reachable else PALETTE["danger"]
    status = "Online" if reachable else "Offline"
    tags = "".join(f'<span class="atlas-tag">{html.escape(s)}</span>' for s in skills[:6])
    if not tags:
        tags = '<span class="atlas-tag">no skills</span>'
    st.markdown(
        f"""
        <div class="atlas-card">
          <div class="atlas-card-title">
            <span class="atlas-status-dot" style="background:{dot};"></span>
            {html.escape(name)} · :{html.escape(port)}
          </div>
          <div style="color:{PALETTE['text_muted']};font-size:0.85rem;margin-bottom:0.5rem;">
            {status}
          </div>
          {tags}
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_card(
    title: str,
    severity: str,
    summary: str,
    *,
    evidence: str = "",
    context: str = "",
) -> None:
    """Alert card with severity-colored left border."""
    border = SEVERITY_COLORS.get(str(severity).upper(), PALETTE["border"])
    st.markdown(
        f"""
        <div class="atlas-alert-card" style="border-left-color:{border};">
          <div class="atlas-card-title">{html.escape(title)}</div>
          <div style="margin-bottom:0.5rem;">{_pill(severity, border)}</div>
          <div style="color:{PALETTE['text']};">{html.escape(summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if evidence:
        with st.expander("Evidence"):
            st.markdown(evidence)
    if context:
        with st.expander("Context"):
            st.markdown(context)


def topic_card(title: str, confidence: str, analysis: str, *, delta: str = "") -> None:
    """Expandable-style topic section for briefings."""
    conf_color = CONFIDENCE_COLORS.get(confidence.upper(), CONFIDENCE_COLORS["LOW"])
    st.markdown(
        f"""
        <div class="atlas-card" style="border-left:4px solid {conf_color};">
          <div class="atlas-card-title">{html.escape(title)}</div>
          {_pill(confidence, conf_color)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(analysis)
    if delta:
        st.caption(delta)


def delta_callout(text: str) -> None:
    """Highlighted delta section for briefings."""
    st.markdown(
        f'<div class="atlas-callout">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def source_list(sources: list[JsonDict] | dict[str, Any]) -> None:
    """Render formatted source citations."""
    if isinstance(sources, dict):
        for agent, agent_sources in sources.items():
            with st.expander(f"{agent} sources"):
                if isinstance(agent_sources, list):
                    st.json(agent_sources)
                else:
                    st.write(agent_sources)
        return

    if not sources:
        st.caption("No sources recorded.")
        return

    for index, source in enumerate(sources, start=1):
        label = source.get("tool") or source.get("type") or source.get("agent") or f"Source {index}"
        with st.expander(str(label)):
            st.json(source)


def duration_color(duration_ms: float) -> str:
    """Return CSS color for span duration (green <1s, yellow 1-5s, red >5s)."""
    if duration_ms >= 5000:
        return PALETTE["danger"]
    if duration_ms >= 1000:
        return PALETTE["warning"]
    return PALETTE["success"]


def _span_node_html(node: JsonDict, *, depth: int = 0) -> str:
    duration = float(node.get("duration_ms") or 0)
    color = duration_color(duration)
    name = html.escape(str(node.get("name", "span")))
    attrs = node.get("attributes") or {}
    attr_items = "".join(
        f"<li><code>{html.escape(str(k))}</code>: {html.escape(str(v))}</li>"
        for k, v in list(attrs.items())[:8]
    )
    children = node.get("children") or []
    child_html = "".join(_span_node_html(child, depth=depth + 1) for child in children)
    inner = f"""
      <div class="trace-meta" style="color:{color};">{duration:.1f} ms</div>
      {f'<ul class="trace-attrs">{attr_items}</ul>' if attr_items else ''}
      {child_html}
    """
    if children or attr_items:
        open_attr = " open" if depth < 1 else ""
        return f"""
        <details class="trace-node" style="margin-left:{depth * 14}px;"{open_attr}>
          <summary><strong>{name}</strong> <span style="color:{color};">({duration:.1f} ms)</span></summary>
          {inner}
        </details>
        """
    return f"""
    <div class="trace-leaf" style="margin-left:{depth * 14}px;">
      <strong>{name}</strong> <span style="color:{color};">({duration:.1f} ms)</span>
    </div>
    """


def render_trace_tree_html(nodes: list[JsonDict], *, height: int = 520) -> None:
    """Render interactive HTML/CSS trace tree."""
    body = "".join(_span_node_html(node) for node in nodes)
    tree_html = f"""
    <!DOCTYPE html>
    <html><head><style>
      body {{
        font-family: ui-sans-serif, system-ui, sans-serif;
        background: {PALETTE["surface"]};
        color: {PALETTE["text"]};
        margin: 0; padding: 12px; font-size: 13px;
      }}
      details {{ margin: 4px 0; }}
      summary {{ cursor: pointer; padding: 4px 0; }}
      summary:hover {{ color: {PALETTE["accent"]}; }}
      .trace-attrs {{ margin: 6px 0 8px 18px; color: {PALETTE["text_muted"]}; font-size: 12px; }}
      .trace-leaf {{ padding: 3px 0; }}
    </style></head>
    <body>{body}</body></html>
    """
    components.html(tree_html, height=height, scrolling=True)


def render_span_tree(nodes: list[JsonDict], *, depth: int = 0) -> None:
    """Fallback expandable span tree (plain Streamlit)."""
    for node in nodes:
        duration = float(node.get("duration_ms") or 0)
        color = duration_color(duration)
        attrs = node.get("attributes") or {}
        attr_text = ", ".join(f"{k}={v}" for k, v in list(attrs.items())[:6])
        label = f"{node.get('name')} ({duration:.1f} ms)"
        with st.expander(label, expanded=depth == 0):
            st.markdown(
                f'<span style="color:{color};font-weight:600;">Duration: {duration:.1f} ms</span>',
                unsafe_allow_html=True,
            )
            if attr_text:
                st.caption(attr_text)
            if attrs:
                st.json(attrs)
            children = node.get("children") or []
            if children:
                render_span_tree(children, depth=depth + 1)


def service_down_message(title: str, detail: str) -> None:
    """Show a friendly unavailable-services message."""
    st.error(f"**{title}** — {detail}")
