"""Phase 8 demo: generate one scheduled-style briefing immediately."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

from agents.geopolitical.agent import GeopoliticalRiskAgent
from agents.guardian.agent import GuardianAgent
from agents.market.agent import DEFAULT_MCP_URL, MarketIntelligenceAgent
from agents.research.agent import DEFAULT_EDGAR_MCP_URL, ResearchFilingAgent
from agents.supply_chain.agent import SupplyChainAgent
from agents.synthesis.agent import SynthesisAgent
from memory.episodic import EpisodicMemory
from protocols.a2a.discovery import load_cards
from protocols.a2a.server import A2AServer
from protocols.mcp.client import McpClient
from services.briefing import BriefingEngine
from services.briefing_templates import format_daily_briefing, format_summary_line


async def wait_for_agent_cards(urls: list[str], *, timeout_seconds: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    pending = set(urls)
    async with httpx.AsyncClient(timeout=1.0) as client:
        while pending and asyncio.get_running_loop().time() < deadline:
            for url in list(pending):
                try:
                    response = await client.get(f"{url.rstrip('/')}/.well-known/agent.json")
                    if response.status_code == 200:
                        pending.remove(url)
                except httpx.HTTPError:
                    pass
            await asyncio.sleep(0.25)
    if pending:
        raise RuntimeError(f"A2A servers did not become ready: {sorted(pending)}")


def start_agent_servers() -> list[A2AServer]:
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


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Briefing Demo (Phase 8)")
    print("Prerequisites: Ollama running, MCP market :8001, MCP EDGAR :8002")
    print("This default watchlist run may take several minutes.")
    print("-" * 80)

    servers = start_agent_servers()
    try:
        await wait_for_agent_cards(
            [
                "http://localhost:9001",
                "http://localhost:9002",
                "http://localhost:9003",
                "http://localhost:9004",
            ]
        )
        registry = load_cards("agents")
        agent_cards = [
            card
            for card in registry.discover_all()
            if "guardian" not in str(card.get("name", "")).lower()
        ]
        episodic_memory = EpisodicMemory()
        synthesis_agent = SynthesisAgent(agent_cards, episodic_memory=episodic_memory)
        engine = BriefingEngine(
            synthesis_agent,
            episodic_memory=episodic_memory,
            guardian=GuardianAgent(),
            briefing_type="daily",
        )
        briefing = await engine.generate_briefing()
        print("\n" + format_daily_briefing(briefing))
        print("\nSummary:")
        print(format_summary_line(briefing))
    finally:
        for server in servers:
            server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
