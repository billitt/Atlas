"""Phase 4 demo: multi-agent synthesis over A2A + LangGraph."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

from agents.geopolitical.agent import GeopoliticalRiskAgent
from agents.market.agent import DEFAULT_MCP_URL, MarketIntelligenceAgent
from agents.supply_chain.agent import SupplyChainAgent
from agents.synthesis.agent import SynthesisAgent
from orchestration.graph import build_synthesis_graph
from protocols.a2a.discovery import load_cards
from protocols.a2a.server import A2AServer
from protocols.mcp.client import McpClient


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


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = (
        "What's the exposure risk if Taiwan Strait tensions escalate? "
        "Consider semiconductor supply chains and market impact."
    )

    print("Atlas Synthesis Demo (Phase 4)")
    print("Prerequisites: Ollama running, Rust MCP server on http://localhost:8001")
    print(f"Query: {query}")
    print("-" * 80)

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
    ]

    for server in servers:
        server.start_background()

    try:
        urls = ["http://localhost:9001", "http://localhost:9002", "http://localhost:9003"]
        await wait_for_agent_cards(urls)

        registry = load_cards("agents")
        agent_cards = registry.discover_all()
        print("Discovered local Agent Cards:")
        for card in agent_cards:
            skills = ", ".join(skill["id"] for skill in card.get("skills", []))
            print(f"  - {card['name']} at {card['url']} [{skills}]")

        synthesis_agent = SynthesisAgent(agent_cards)
        app = build_synthesis_graph(synthesis_agent)

        final_state = await app.ainvoke(
            {
                "query": query,
                "messages": [("user", query)],
                "agent_cards": agent_cards,
                "agent_results": [],
                "sources": [],
            }
        )
        briefing = final_state["briefing"]

        print("\n" + "=" * 80)
        print("SYNTHESIZED BRIEFING")
        print("=" * 80)
        print(f"\nOverall confidence: {briefing['overall_confidence']}\n")
        print(briefing["combined_analysis"])

        print("\nExecution plan:")
        print(json.dumps(briefing["execution_plan"], indent=2))

        print("\nPer-agent sources:")
        print(json.dumps(briefing["per_agent_sources"], indent=2))
    finally:
        for server in servers:
            server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
