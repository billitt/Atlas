"""Atlas API runtime — boots A2A agents and reuses CLI synthesis builders."""

from __future__ import annotations

from typing import Any

import httpx

from cli.main import _build_synthesis_stack, _collect_status
from examples._demo_infra import (
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from protocols.a2a.discovery import load_cards
from protocols.a2a.server import A2AServer
from protocols.auth import a2a_auth_token, auth_headers

from api.config import a2a_agent_urls

JsonDict = dict[str, Any]

AGENT_ENDPOINTS = (
    ("Market Intelligence", a2a_agent_urls()[0]),
    ("Geopolitical Risk", a2a_agent_urls()[1]),
    ("Supply Chain", a2a_agent_urls()[2]),
    ("Research & Filing", a2a_agent_urls()[3]),
)


def _check_prerequisites(
    *, require_mcp: bool = True, require_ollama: bool = True
) -> tuple[bool, list[str]]:
    """Return readiness and human-readable issue messages."""
    status = _collect_status()
    issues: list[str] = []

    if require_ollama:
        if not status.get("ollama", {}).get("reachable"):
            issues.append("Ollama is not reachable. Start Ollama and pull Granite.")
        elif not status.get("ollama", {}).get("model_loaded"):
            issues.append(
                f"Model {status.get('ollama', {}).get('model')} is not loaded. "
                "Run: ollama pull ibm/granite4.1:8b"
            )

    if require_mcp:
        for server in status.get("mcp_servers") or []:
            if not server.get("reachable"):
                name = server.get("name", "mcp")
                if "market" in name:
                    issues.append(
                        f"{name} down on {server.get('url')} — "
                        "run: cargo run -p mcp-market-data"
                    )
                elif "edgar" in name:
                    issues.append(
                        f"{name} down on {server.get('url')} — run: cargo run -p mcp-edgar"
                    )
                elif "trade" in name:
                    issues.append(
                        f"{name} down on {server.get('url')} — run: cargo run -p mcp-trade"
                    )
                else:
                    issues.append(f"{name} down on {server.get('url')}")

    return len(issues) == 0, issues


def _fetch_agent_cards_status() -> list[JsonDict]:
    """Probe A2A agent card endpoints."""
    cards: list[JsonDict] = []
    for name, url in AGENT_ENDPOINTS:
        reachable = False
        skills: list[str] = []
        try:
            with httpx.Client(timeout=2.0, headers=auth_headers(a2a_auth_token())) as client:
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


def collect_status_payload() -> JsonDict:
    """System health snapshot for /api/status."""
    status = _collect_status()
    ready, issues = _check_prerequisites(require_mcp=True, require_ollama=True)
    status["ready"] = ready
    status["issues"] = issues
    status["agents"] = _fetch_agent_cards_status()
    return status


async def boot_agent_runtime() -> tuple[list[JsonDict], list[A2AServer]]:
    """Start MCP check, A2A servers, and load agent cards."""
    await start_mcp_check()
    servers = start_agent_servers()
    await wait_for_agent_cards(list(a2a_agent_urls()))
    registry = load_cards("agents")
    agent_cards = [
        card
        for card in registry.discover_all()
        if "guardian" not in str(card.get("name", "")).lower()
    ]
    return agent_cards, servers


def shutdown_agent_servers(servers: list[A2AServer]) -> None:
    for server in servers:
        server.shutdown()


def build_synthesis_stack(agent_cards: list[JsonDict]) -> tuple[Any, Any]:
    return _build_synthesis_stack(agent_cards)
