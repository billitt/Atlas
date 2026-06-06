"""Atlas Intelligence Platform — Streamlit dashboard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from ui.runtime import ensure_agent_runtime, get_status
from ui.styles import global_css
from ui.views import agent_status, alerts, briefings, query, trace_viewer

PAGES = {
    "Query": query.render,
    "Briefings": briefings.render,
    "Alerts": alerts.render,
    "Agent Status": agent_status.render,
    "Trace Viewer": trace_viewer.render,
}


def render_sidebar_status() -> None:
    """Compact system status in the sidebar."""
    status = get_status()
    ollama = status.get("ollama") or {}
    memory = status.get("memory") or {}

    st.sidebar.markdown("### System Status")
    st.sidebar.caption(
        f"Ollama: {'🟢' if ollama.get('reachable') else '🔴'} · "
        f"Model: {'🟢' if ollama.get('model_loaded') else '🟡'}"
    )
    for server in status.get("mcp_servers") or []:
        icon = "🟢" if server.get("reachable") else "🔴"
        st.sidebar.caption(f"{icon} {server.get('name')}")

    st.sidebar.caption(
        f"Memory: {memory.get('semantic_docs', 0)} semantic · "
        f"{memory.get('episodic_briefings', 0)} briefings"
    )

    if st.session_state.get("agent_boot_error"):
        st.sidebar.error("A2A agents: failed to start")
    elif st.session_state.get("agent_cards"):
        st.sidebar.success("A2A agents: running")
    elif st.session_state.get("agent_boot_in_progress"):
        st.sidebar.caption("A2A agents: starting...")
    else:
        st.sidebar.caption("A2A agents: idle")


def run_dashboard() -> None:
    """Render the Streamlit dashboard (called on each Streamlit rerun)."""
    st.set_page_config(
        page_title="Atlas Intelligence Platform",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(global_css(), unsafe_allow_html=True)

    if not st.session_state.get("agents_started"):
        st.session_state.agents_started = True
        ensure_agent_runtime()

    st.sidebar.title("Atlas")
    st.sidebar.caption("Global Intelligence Platform")

    if st.session_state.get("trace_viewer_id"):
        default_page = "Trace Viewer"
    else:
        default_page = "Query"

    page_names = list(PAGES.keys())
    default_index = page_names.index(default_page) if default_page in page_names else 0
    page = st.sidebar.radio("Navigation", page_names, index=default_index)

    render_sidebar_status()
    PAGES[page]()


def main() -> None:
    """Launch Streamlit via `atlas-dashboard` entry point."""
    app_path = Path(__file__).resolve()
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]])
    )


def _streamlit_script_active() -> bool:
    """True when Streamlit is executing this file (not a plain Python import)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except ImportError:
        return False


if _streamlit_script_active():
    run_dashboard()
elif __name__ == "__main__":
    main()
