"""Agent health and capabilities view."""

from __future__ import annotations

import streamlit as st

from ui.components import agent_status_card, metric_card
from ui.runtime import fetch_agent_cards_status, get_ollama_vram, get_status


def render() -> None:
    st.header("Agent & System Status")
    st.caption("Live health for Ollama, MCP servers, A2A agents, and memory tiers")

    status = get_status()
    ollama = status.get("ollama") or {}
    memory = status.get("memory") or {}

    st.subheader("Ollama")
    ollama_ok = ollama.get("reachable") and ollama.get("model_loaded")
    row = st.columns(4)
    with row[0]:
        metric_card(
            "Reachable",
            "Yes" if ollama.get("reachable") else "No",
            status="ok" if ollama.get("reachable") else "error",
        )
    with row[1]:
        metric_card("Model", str(ollama.get("model", "unknown")))
    with row[2]:
        metric_card(
            "Loaded",
            "Yes" if ollama.get("model_loaded") else "No",
            status="ok" if ollama.get("model_loaded") else "warn",
        )
    with row[3]:
        vram = get_ollama_vram()
        metric_card("VRAM", vram or "N/A", status="ok" if vram else None)

    st.divider()
    st.subheader("MCP Servers")
    mcp_servers = status.get("mcp_servers") or []
    if mcp_servers:
        mcp_cols = st.columns(len(mcp_servers))
        for col, server in zip(mcp_cols, mcp_servers, strict=False):
            with col:
                metric_card(
                    str(server.get("name", "MCP")),
                    "Online" if server.get("reachable") else "Offline",
                    status="ok" if server.get("reachable") else "error",
                )
                st.caption(str(server.get("url", "")))
                if not server.get("reachable"):
                    if "market" in str(server.get("name")):
                        st.code("cargo run -p mcp-market-data", language="powershell")
                    else:
                        st.code("cargo run -p mcp-edgar", language="powershell")

    st.divider()
    st.subheader("A2A Agents")
    agents = fetch_agent_cards_status()
    for row_start in range(0, len(agents), 2):
        cols = st.columns(2)
        for col, agent in zip(cols, agents[row_start : row_start + 2], strict=False):
            with col:
                agent_status_card(
                    agent["name"],
                    agent["port"],
                    agent["reachable"],
                    agent["skills"],
                )

    st.divider()
    st.subheader("Memory")
    m1, m2, m3 = st.columns(3)
    with m1:
        metric_card("Semantic docs", str(memory.get("semantic_docs", 0)))
    with m2:
        metric_card("Episodic briefings", str(memory.get("episodic_briefings", 0)))
    with m3:
        metric_card("Episodic alerts", str(memory.get("episodic_alerts", 0)))

    last_briefing = status.get("last_briefing")
    last_alert = status.get("last_alert")
    if last_briefing or last_alert:
        st.divider()
        st.subheader("Recent activity")
        if last_briefing:
            st.markdown(
                f"**Last briefing:** {last_briefing.get('timestamp')} — "
                f"{last_briefing.get('query', '')[:80]}"
            )
            st.caption(f"Confidence: {last_briefing.get('confidence')}")
        if last_alert:
            st.markdown(
                f"**Last alert:** {last_alert.get('timestamp')} — {last_alert.get('rule_name')}"
            )

    if not ollama_ok:
        st.warning("Start Ollama and pull Granite before running queries or briefings.")
