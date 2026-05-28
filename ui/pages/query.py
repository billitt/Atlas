"""Natural language Q&A page."""

from __future__ import annotations

import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any

import streamlit as st

from agents.guardian.agent import GuardianAgent
from observability.run_logger import save_run
from observability.tracing import get_current_trace_id
from orchestration.graph import build_synthesis_graph, run_synthesis_graph
from ui.components import confidence_badge, guardian_badge, source_list
from ui.runtime import build_synthesis_stack, get_agent_cards, show_prerequisite_warnings

JsonDict = dict[str, Any]


def render() -> None:
    st.header("Natural Language Query")
    st.caption("Run the full synthesis pipeline: LangGraph → A2A → agents → Guardian")

    ready = show_prerequisite_warnings(require_mcp=True, require_ollama=True)
    query = st.text_area(
        "Your question",
        placeholder="What's the TSMC risk exposure if Taiwan Strait tensions escalate?",
        height=100,
    )

    if st.session_state.get("agent_boot_error"):
        st.error(f"A2A agents failed to start: {st.session_state.agent_boot_error}")

    run_disabled = not ready or not query.strip()
    if st.button("Run Analysis", type="primary", disabled=run_disabled):
        agent_cards = get_agent_cards()
        if not agent_cards:
            st.error("Could not start A2A agent servers. Check MCP servers and try refreshing.")
            return

        async def _run_pipeline() -> JsonDict:
            synthesis_agent, episodic_memory = build_synthesis_stack(agent_cards)
            app_graph = build_synthesis_graph(synthesis_agent, guardian=GuardianAgent())
            started_at = datetime.now().isoformat(timespec="seconds")
            start_time = perf_counter()
            final_state = await run_synthesis_graph(
                app_graph,
                {
                    "query": query.strip(),
                    "messages": [("user", query.strip())],
                    "agent_cards": agent_cards,
                    "agent_results": [],
                    "sources": [],
                    "guardian_retries": 0,
                },
            )
            duration_seconds = round(perf_counter() - start_time, 3)
            briefing = final_state["briefing"]
            trace_id = get_current_trace_id()
            guardian_verdict = briefing.get("guardian_verdict", {})
            run_data = {
                "timestamp": started_at,
                "query": query.strip(),
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
            return {
                "briefing": briefing,
                "trace_id": trace_id,
                "duration_seconds": duration_seconds,
            }

        with st.spinner("Agents working..."):
            try:
                result = asyncio.run(_run_pipeline())
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                return

        st.session_state.last_query_result = result
        st.success(f"Analysis complete in {result['duration_seconds']}s")

    result = st.session_state.get("last_query_result")
    if not result:
        if not ready:
            st.info("Start Ollama and MCP servers to enable queries.")
        return

    briefing = result["briefing"]
    trace_id = result.get("trace_id")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Confidence")
        confidence_badge(briefing.get("overall_confidence", "LOW"))
    with col2:
        st.subheader("Guardian")
        guardian = briefing.get("guardian_verdict") or {}
        guardian_badge(bool(guardian.get("passed", False)))

    with st.expander("Combined analysis", expanded=True):
        st.markdown(briefing.get("combined_analysis", ""))

    with st.expander("Guardian verdict"):
        st.json(guardian)
        flags = guardian.get("flags") or []
        if flags:
            st.warning("Flags: " + "; ".join(flags))

    per_agent = briefing.get("agent_results") or []
    with st.expander("Per-agent contributions"):
        for entry in per_agent:
            agent_name = entry.get("agent") or entry.get("name") or "agent"
            with st.expander(str(agent_name)):
                artifact = entry.get("artifact", {})
                metadata = artifact.get("metadata", {})
                st.markdown(metadata.get("analysis") or artifact.get("text") or str(entry))

    with st.expander("Sources"):
        source_list(briefing.get("per_agent_sources") or {})

    if trace_id:
        if st.button("Open in Trace Viewer"):
            st.session_state.trace_viewer_id = trace_id
            st.rerun()
        st.caption(f"trace_id: `{trace_id}`")
