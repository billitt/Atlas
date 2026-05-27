"""Agent health and capabilities page."""

from __future__ import annotations

import streamlit as st

from ui.components import agent_status_card
from ui.runtime import fetch_agent_cards_status, get_ollama_vram, get_status


def render() -> None:
    st.header("Agent & System Status")
    st.caption("Live health for Ollama, MCP servers, A2A agents, and memory tiers")

    status = get_status()
    ollama = status.get("ollama") or {}

    st.subheader("Ollama")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Reachable", "Yes" if ollama.get("reachable") else "No")
    with col2:
        st.metric("Model", ollama.get("model", "unknown"))
    with col3:
        st.metric("Model loaded", "Yes" if ollama.get("model_loaded") else "No")
    vram = get_ollama_vram()
    if vram:
        st.caption(f"VRAM: {vram}")
    elif ollama.get("reachable"):
        st.caption("VRAM info unavailable from Ollama /api/ps")

    st.divider()
    st.subheader("MCP Servers")
    mcp_cols = st.columns(len(status.get("mcp_servers") or [1]))
    for col, server in zip(mcp_cols, status.get("mcp_servers") or [], strict=False):
        with col:
            with st.container(border=True):
                st.markdown(f"**{server.get('name')}**")
                st.caption(server.get("url", ""))
                st.metric("Status", "Online" if server.get("reachable") else "Offline")
                if not server.get("reachable"):
                    if "market" in str(server.get("name")):
                        st.code("cargo run -p mcp-market-data", language="powershell")
                    else:
                        st.code("cargo run -p mcp-edgar", language="powershell")

    st.divider()
    st.subheader("A2A Agents")
    agents = fetch_agent_cards_status()
    agent_cols = st.columns(2)
    for index, agent in enumerate(agents):
        with agent_cols[index % 2]:
            agent_status_card(
                agent["name"],
                agent["port"],
                agent["reachable"],
                agent["skills"],
            )

    st.divider()
    st.subheader("Memory")
    memory = status.get("memory") or {}
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Semantic docs", memory.get("semantic_docs", 0))
    with m2:
        st.metric("Episodic briefings", memory.get("episodic_briefings", 0))
    with m3:
        st.metric("Episodic alerts", memory.get("episodic_alerts", 0))

    last_briefing = status.get("last_briefing")
    last_alert = status.get("last_alert")
    if last_briefing or last_alert:
        st.divider()
        st.subheader("Recent activity")
        if last_briefing:
            st.markdown(f"**Last briefing:** {last_briefing.get('timestamp')} — {last_briefing.get('query', '')[:80]}")
            st.caption(f"Confidence: {last_briefing.get('confidence')}")
        if last_alert:
            st.markdown(f"**Last alert:** {last_alert.get('timestamp')} — {last_alert.get('rule_name')}")
