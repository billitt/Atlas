"""Briefing viewer."""

from __future__ import annotations

import asyncio
from typing import Any

import streamlit as st
from sqlmodel import Session, select

from agents.guardian.agent import GuardianAgent
from memory.episodic import BriefingRecord, EpisodicMemory
from services.briefing import DEFAULT_WATCHLIST, BriefingEngine
from ui.components import confidence_badge, delta_callout, guardian_badge, severity_badge
from ui.runtime import build_synthesis_stack, get_agent_cards, show_prerequisite_warnings

JsonDict = dict[str, Any]


def render() -> None:
    st.header("Briefings")
    st.caption("Generate watchlist briefings or browse episodic history")

    ready = show_prerequisite_warnings(require_mcp=True, require_ollama=True)

    briefing_type = st.selectbox("Briefing type", ["daily", "weekly", "custom"], index=0)
    default_topics = list(DEFAULT_WATCHLIST)
    selected = st.multiselect("Watchlist topics", default_topics, default=default_topics)
    custom_topic = st.text_input("Add custom topic (optional)")
    topics = selected.copy()
    if custom_topic.strip():
        topics.append(custom_topic.strip())

    if st.button("Generate Briefing", type="primary", disabled=not ready or not topics):
        agent_cards = get_agent_cards()
        if not agent_cards:
            st.error("Could not start A2A agent servers.")
            return

        async def _generate() -> JsonDict:
            synthesis_agent, episodic_memory = build_synthesis_stack(agent_cards)
            engine = BriefingEngine(
                synthesis_agent,
                episodic_memory=episodic_memory,
                guardian=GuardianAgent(),
                briefing_type=briefing_type,
            )
            return await engine.generate_briefing(topics)

        with st.spinner("Generating briefing across topics..."):
            try:
                briefing = asyncio.run(_generate())
            except Exception as exc:
                st.error(f"Briefing failed: {exc}")
                return

        st.session_state.last_briefing = briefing
        st.success("Briefing generated")

    briefing = st.session_state.get("last_briefing")
    if briefing:
        st.divider()
        st.subheader(f"{briefing.get('briefing_type', 'daily').title()} Briefing")
        st.markdown("**Overall risk**")
        severity_badge(briefing.get("overall_risk_level", "LOW"))
        st.caption(f"Generated: {briefing.get('timestamp')}")

        st.markdown("#### What changed")
        delta_callout(briefing.get("delta_from_last") or "No delta available.")

        for section in briefing.get("sections") or []:
            guardian = section.get("guardian_verdict") or {}
            conf = section.get("confidence", "LOW")
            with st.expander(f"📋 {section.get('topic', 'Topic')}", expanded=True):
                col_a, col_b = st.columns(2)
                with col_a:
                    confidence_badge(conf)
                with col_b:
                    guardian_badge(bool(guardian.get("passed", False)))
                st.markdown(section.get("analysis", ""))
                if section.get("delta_from_last"):
                    st.caption(f"Delta: {section['delta_from_last']}")
                if guardian.get("flags"):
                    st.warning("Guardian flags: " + "; ".join(guardian["flags"]))

    st.divider()
    st.subheader("Briefing history")
    episodic = EpisodicMemory()
    with Session(episodic.engine) as session:
        records = list(
            session.exec(select(BriefingRecord).order_by(BriefingRecord.timestamp.desc()).limit(20))
        )

    if not records:
        st.info("No past briefings in episodic memory yet.")
        return

    rows = [
        {
            "timestamp": r.timestamp.isoformat(timespec="seconds"),
            "query": r.query[:80],
            "confidence": r.confidence,
            "type": r.briefing_type,
            "duration_s": r.duration_seconds,
        }
        for r in records
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    selected_id = st.selectbox(
        "Expand a past briefing",
        options=range(len(records)),
        format_func=lambda i: f"{records[i].timestamp} — {records[i].query[:60]}",
    )
    record = records[selected_id]
    with st.expander("Full briefing content", expanded=False):
        st.markdown(f"**Query/topics:** {record.query}")
        confidence_badge(record.confidence)
        st.markdown(record.final_briefing)
