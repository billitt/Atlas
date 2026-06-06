"""Shared runtime helpers for the Atlas Streamlit dashboard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

from cli.main import _build_alert_engine, _build_synthesis_stack, _collect_status
from examples._demo_infra import (
    DEFAULT_AGENT_CARD_URLS,
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from protocols.a2a.discovery import load_cards
from services.llm import OLLAMA_BASE_URL

JsonDict = dict[str, Any]

AGENT_ENDPOINTS = (
    ("Market Intelligence", "http://localhost:9001"),
    ("Geopolitical Risk", "http://localhost:9002"),
    ("Supply Chain", "http://localhost:9003"),
    ("Research & Filing", "http://localhost:9004"),
)


@st.cache_data(ttl=10, show_spinner=False)
def get_status() -> JsonDict:
    """Return system health snapshot (cached 10s for sidebar reruns)."""
    return _collect_status()


@st.cache_data(ttl=15, show_spinner=False)
def fetch_agent_cards_status() -> list[JsonDict]:
    """Probe A2A agent card endpoints for the status page (cached 15s)."""
    cards: list[JsonDict] = []
    for name, url in AGENT_ENDPOINTS:
        reachable = False
        skills: list[str] = []
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{url.rstrip('/')}/.well-known/agent.json")
                reachable = response.status_code == 200
                if reachable:
                    payload = response.json()
                    skills = [
                        skill.get("id", "")
                        for skill in payload.get("skills", [])
                        if skill.get("id")
                    ]
        except httpx.HTTPError:
            pass
        port = url.rsplit(":", 1)[-1]
        cards.append(
            {
                "name": name,
                "url": url,
                "port": port,
                "reachable": reachable,
                "skills": skills,
            }
        )
    return cards


@st.cache_data(ttl=30, show_spinner=False)
def get_ollama_vram() -> str | None:
    """Return VRAM usage string from Ollama /api/ps when available."""
    try:
        with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=2.0) as client:
            response = client.get("/api/ps")
            response.raise_for_status()
            models = response.json().get("models") or []
            if not models:
                return None
            parts = []
            for model in models:
                vram = model.get("size_vram") or model.get("size")
                if vram:
                    gb = round(int(vram) / (1024**3), 2)
                    parts.append(f"{model.get('name', 'model')}: {gb} GB VRAM")
            return "; ".join(parts) if parts else None
    except httpx.HTTPError:
        return None


def check_prerequisites(
    *, require_mcp: bool = True, require_ollama: bool = True
) -> tuple[bool, list[str]]:
    """Return whether required services are up and human-readable issue messages."""
    status = get_status()
    issues: list[str] = []

    if require_ollama:
        if not status.get("ollama", {}).get("reachable"):
            issues.append("Ollama is not reachable. Start Ollama and pull Granite.")
        elif not status.get("ollama", {}).get("model_loaded"):
            issues.append(
                f"Model {status.get('ollama', {}).get('model')} is not loaded. Run: ollama pull ibm/granite4.1:8b"
            )

    if require_mcp:
        for server in status.get("mcp_servers") or []:
            if not server.get("reachable"):
                name = server.get("name", "mcp")
                if "market" in name:
                    issues.append(
                        f"{name} down on {server.get('url')} — run: cargo run -p mcp-market-data"
                    )
                elif "edgar" in name:
                    issues.append(
                        f"{name} down on {server.get('url')} — run: cargo run -p mcp-edgar"
                    )
                else:
                    issues.append(f"{name} down on {server.get('url')}")

    return len(issues) == 0, issues


def show_prerequisite_warnings(*, require_mcp: bool = True, require_ollama: bool = True) -> bool:
    """Display warnings for missing services. Returns True if prerequisites met."""
    ok, issues = check_prerequisites(require_mcp=require_mcp, require_ollama=require_ollama)
    for issue in issues:
        st.warning(issue)
    return ok


def ensure_agent_runtime() -> list[JsonDict]:
    """Start background A2A servers once per Streamlit session and return agent cards."""
    if st.session_state.get("agent_cards"):
        return st.session_state["agent_cards"]

    if st.session_state.get("agent_boot_error"):
        return []

    if st.session_state.get("agent_boot_in_progress"):
        return []

    st.session_state.agent_boot_in_progress = True
    try:
        servers = start_agent_servers()
        st.session_state.agent_servers = servers
        asyncio.run(start_mcp_check())
        asyncio.run(wait_for_agent_cards(DEFAULT_AGENT_CARD_URLS))
        registry = load_cards("agents")
        agent_cards = [
            card
            for card in registry.discover_all()
            if "guardian" not in str(card.get("name", "")).lower()
        ]
        st.session_state.agent_cards = agent_cards
        st.session_state.agent_boot_error = None
        return agent_cards
    except Exception as exc:
        st.session_state.agent_boot_error = str(exc)
        st.session_state.agent_cards = []
        return []
    finally:
        st.session_state.agent_boot_in_progress = False


def get_agent_cards() -> list[JsonDict]:
    """Return cached agent cards, starting servers if needed."""
    return ensure_agent_runtime()


@st.cache_resource(show_spinner=False)
def _cached_synthesis_stack(cards_json: str) -> tuple[Any, Any]:
    """Build synthesis agent + episodic memory once per session/card set."""
    agent_cards: list[JsonDict] = json.loads(cards_json)
    return _build_synthesis_stack(agent_cards)


def build_synthesis_stack(agent_cards: list[JsonDict]) -> tuple[Any, Any]:
    """Build synthesis agent + episodic memory (cached per agent card set)."""
    cards_json = json.dumps(agent_cards, sort_keys=True)
    return _cached_synthesis_stack(cards_json)


@st.cache_resource(show_spinner=False)
def build_alert_engine() -> Any:
    """Return AlertEngine with default rules registered (one instance per session)."""
    return _build_alert_engine()


def find_run_log_by_trace_id(trace_id: str) -> Path | None:
    """Locate a runs/*.json file matching trace_id."""
    runs_dir = Path("runs")
    if not runs_dir.exists():
        return None
    for path in sorted(runs_dir.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("trace_id") == trace_id:
            return path
    return None
