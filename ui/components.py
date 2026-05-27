"""Reusable Streamlit widgets for the Atlas dashboard."""

from __future__ import annotations

from typing import Any

import streamlit as st

JsonDict = dict[str, Any]

_CONFIDENCE_COLORS = {
    "HIGH": "#22c55e",
    "MEDIUM": "#eab308",
    "LOW": "#ef4444",
}

_SEVERITY_COLORS = {
    "HIGH": "#ef4444",
    "MEDIUM": "#eab308",
    "LOW": "#22c55e",
}


def confidence_badge(level: str) -> None:
    """Render a colored confidence badge."""
    key = str(level or "LOW").upper()
    color = _CONFIDENCE_COLORS.get(key, _CONFIDENCE_COLORS["LOW"])
    st.markdown(
        f'<span style="background:{color};color:#111;padding:4px 10px;border-radius:6px;'
        f'font-weight:600;">{key}</span>',
        unsafe_allow_html=True,
    )


def guardian_badge(passed: bool) -> None:
    """Render a green checkmark or red flag for Guardian verdict."""
    if passed:
        st.markdown(
            '<span style="color:#22c55e;font-weight:700;">✓ PASSED</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span style="color:#ef4444;font-weight:700;">⚑ FLAGGED</span>',
            unsafe_allow_html=True,
        )


def severity_badge(severity: str) -> None:
    """Render a colored severity indicator."""
    key = str(severity or "LOW").upper()
    color = _SEVERITY_COLORS.get(key, _SEVERITY_COLORS["LOW"])
    st.markdown(
        f'<span style="background:{color};color:#111;padding:4px 10px;border-radius:6px;'
        f'font-weight:600;">{key}</span>',
        unsafe_allow_html=True,
    )


def agent_status_card(name: str, port: str, reachable: bool, skills: list[str]) -> None:
    """Render a formatted agent status card."""
    status = "🟢 Online" if reachable else "🔴 Offline"
    with st.container(border=True):
        st.markdown(f"**{name}** — port `{port}`")
        st.caption(status)
        if skills:
            st.write("Skills: " + ", ".join(skills))
        else:
            st.caption("No skills discovered")


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
    """Return CSS color for span duration highlighting."""
    if duration_ms >= 10000:
        return "#ef4444"
    if duration_ms >= 3000:
        return "#eab308"
    return "#94a3b8"


def render_span_tree(nodes: list[JsonDict], *, depth: int = 0) -> None:
    """Render expandable span tree with duration color-coding."""
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
