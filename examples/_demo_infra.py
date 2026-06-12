"""Shared infrastructure for Atlas multi-agent demos (not a standalone demo)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from agents.geopolitical.agent import GeopoliticalRiskAgent
from agents.market.agent import DEFAULT_MCP_URL, MarketIntelligenceAgent
from agents.research.agent import DEFAULT_EDGAR_MCP_URL, ResearchFilingAgent
from agents.supply_chain.agent import SupplyChainAgent
from protocols.a2a.server import A2AServer
from protocols.auth import a2a_auth_token, auth_headers, mcp_auth_token
from protocols.mcp.client import McpClient

DEFAULT_MCP_URLS = (DEFAULT_MCP_URL, DEFAULT_EDGAR_MCP_URL)
DEFAULT_AGENT_CARD_URLS = (
    "http://localhost:9001",
    "http://localhost:9002",
    "http://localhost:9003",
    "http://localhost:9004",
)


async def start_mcp_check(
    urls: list[str] | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    """Verify Rust MCP servers respond on GET /health before starting agents."""
    pending = set(urls or DEFAULT_MCP_URLS)
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with httpx.AsyncClient(
        timeout=1.0,
        headers=auth_headers(mcp_auth_token()),
    ) as client:
        while pending and asyncio.get_running_loop().time() < deadline:
            for url in list(pending):
                try:
                    response = await client.get(f"{url.rstrip('/')}/health")
                    if response.status_code == 200:
                        pending.remove(url)
                except httpx.HTTPError:
                    pass
            if pending:
                await asyncio.sleep(0.25)
    if pending:
        raise RuntimeError(
            f"MCP servers did not become ready: {sorted(pending)} "
            "(start with: cargo run -p mcp-market-data, cargo run -p mcp-edgar)"
        )


async def wait_for_agent_cards(
    urls: list[str] | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    """Poll A2A agent card endpoints until all servers respond."""
    pending = set(urls or DEFAULT_AGENT_CARD_URLS)
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with httpx.AsyncClient(
        timeout=1.0,
        headers=auth_headers(a2a_auth_token()),
    ) as client:
        while pending and asyncio.get_running_loop().time() < deadline:
            for url in list(pending):
                try:
                    response = await client.get(f"{url.rstrip('/')}/.well-known/agent.json")
                    if response.status_code == 200:
                        pending.remove(url)
                except httpx.HTTPError:
                    pass
            if pending:
                await asyncio.sleep(0.25)
    if pending:
        raise RuntimeError(f"A2A servers did not become ready: {sorted(pending)}")


def start_agent_servers() -> list[A2AServer]:
    """Start background A2A servers for all four specialist agents."""
    servers = [
        A2AServer(
            agent=MarketIntelligenceAgent(McpClient(DEFAULT_MCP_URL)),
            agent_card_path=Path("agents/market/agent_card.json"),
            host="127.0.0.1",
            port=9001,
        ),
        A2AServer(
            agent=GeopoliticalRiskAgent(),
            agent_card_path=Path("agents/geopolitical/agent_card.json"),
            host="127.0.0.1",
            port=9002,
        ),
        A2AServer(
            agent=SupplyChainAgent(),
            agent_card_path=Path("agents/supply_chain/agent_card.json"),
            host="127.0.0.1",
            port=9003,
        ),
        A2AServer(
            agent=ResearchFilingAgent(McpClient(DEFAULT_EDGAR_MCP_URL)),
            agent_card_path=Path("agents/research/agent_card.json"),
            host="127.0.0.1",
            port=9004,
        ),
    ]
    for server in servers:
        server.start_background()
    return servers
