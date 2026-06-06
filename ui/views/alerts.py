"""Alert feed view."""

from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from typing import Any

import streamlit as st
from sqlmodel import Session, select

from memory.episodic import AlertRecord, EpisodicMemory
from services.alert_defaults import default_alert_rules
from ui.components import alert_card, severity_badge
from ui.runtime import build_alert_engine, show_prerequisite_warnings

JsonDict = dict[str, Any]


def _run_watch_tick() -> None:
    if not st.session_state.get("watching"):
        return
    interval = int(st.session_state.get("watch_interval", 300))
    now = time.time()
    if now - st.session_state.get("last_watch_check", 0) < interval:
        return
    st.session_state.last_watch_check = now
    try:
        engine = build_alert_engine()
        triggered = asyncio.run(engine.check_all_rules())
        if triggered:
            st.session_state.watch_results = st.session_state.get("watch_results", []) + [
                dict(item) for item in triggered
            ]
    except Exception as exc:
        st.session_state.watch_error = str(exc)
        st.session_state.watching = False


@st.fragment(run_every=timedelta(seconds=30))
def watch_fragment() -> None:
    """Periodic alert checks while watch mode is active."""
    _run_watch_tick()


def render() -> None:
    st.header("Alerts")
    st.caption("Check default rules or run a background watch loop")

    mcp_ok = show_prerequisite_warnings(require_mcp=True, require_ollama=True)

    st.subheader("Active rules")
    cols = st.columns(2)
    for index, rule in enumerate(default_alert_rules()):
        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{rule.name}**")
                severity_badge(rule.severity)
                st.caption(rule.description)
                st.caption(f"ID: `{rule.id}` · cooldown {rule.cooldown_seconds}s")

    st.divider()

    if st.button("Check Now", type="primary", disabled=not mcp_ok):
        with st.spinner("Checking alert rules..."):
            try:
                engine = build_alert_engine()
                triggered = asyncio.run(engine.check_all_rules())
            except Exception as exc:
                st.error(f"Alert check failed: {exc}")
                triggered = []

        if not triggered:
            st.success("No alerts triggered.")
        else:
            for alert in triggered:
                alert_card(
                    f"🚨 {alert['rule_name']}",
                    str(alert.get("severity", "LOW")),
                    str(alert.get("summary", "")),
                    evidence=str(alert.get("evidence", "")),
                    context=str(alert.get("context", "")),
                )

    st.divider()
    st.subheader("Watch loop")

    if "watch_results" not in st.session_state:
        st.session_state.watch_results = []
    if "watch_error" not in st.session_state:
        st.session_state.watch_error = None

    interval = st.number_input("Check interval (seconds)", min_value=30, value=300, step=30)
    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("Start Watch", disabled=not mcp_ok or st.session_state.get("watching")):
            st.session_state.watching = True
            st.session_state.watch_interval = int(interval)
            st.session_state.last_watch_check = 0
            st.session_state.watch_error = None
            st.success(f"Watching every {interval}s — keep this tab open.")
            st.rerun()
    with col_stop:
        if st.button("Stop Watch", disabled=not st.session_state.get("watching")):
            st.session_state.watching = False
            st.info("Watch stopped.")
            st.rerun()

    if st.session_state.get("watching"):
        watch_fragment()
        st.caption(f"Auto-checking every {st.session_state.get('watch_interval', interval)}s")

    if st.session_state.get("watch_error"):
        st.error(st.session_state.watch_error)

    for alert in reversed(st.session_state.get("watch_results") or []):
        alert_card(
            f"Watch: {alert.get('rule_name')} — {alert.get('triggered_at')}",
            str(alert.get("severity", "LOW")),
            str(alert.get("summary", "")),
            evidence=str(alert.get("evidence", "")),
        )

    st.divider()
    st.subheader("Alert history")

    episodic = EpisodicMemory()
    with Session(episodic.engine) as session:
        records = list(
            session.exec(select(AlertRecord).order_by(AlertRecord.timestamp.desc()).limit(30))
        )

    if not records:
        st.info("No alerts in episodic memory yet. Run Check Now to evaluate rules.")
        return

    for record in records:
        with st.expander(
            f"{record.timestamp} — {record.rule_name} [{record.severity}]",
            expanded=False,
        ):
            alert_card(
                record.rule_name,
                record.severity,
                record.summary,
                evidence=record.evidence,
                context=record.context,
            )
