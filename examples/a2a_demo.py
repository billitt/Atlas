"""Phase 3 demo: discover an A2A agent and delegate a task to it."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

from agents.market.agent import DEFAULT_MCP_URL, MarketIntelligenceAgent
from protocols.a2a.client import A2AClient
from protocols.a2a.discovery import load_cards
from protocols.a2a.server import A2AServer
from protocols.mcp.client import McpClient

MARKET_A2A_URL = "http://localhost:9001"


async def wait_for_server(url: str, *, timeout_seconds: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with httpx.AsyncClient(timeout=1.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                response = await client.get(f"{url}/.well-known/agent.json")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError(f"A2A server did not become ready: {url}")


async def run() -> None:
    # Windows consoles default to cp1252; Granite may emit Unicode punctuation.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas A2A Demo (Phase 3)")
    print("Prerequisites: Ollama running, Rust MCP server on http://localhost:8001")
    print("-" * 72)

    registry = load_cards("agents")
    print("Local Agent Cards:")
    for card in registry.discover_all():
        skills = ", ".join(skill["id"] for skill in card.get("skills", []))
        print(f"  - {card['name']} at {card['url']} [{skills}]")

    market_cards = registry.find_by_skill("market_snapshot")
    if not market_cards:
        raise RuntimeError("No registered agent advertises skill 'market_snapshot'")

    mcp = McpClient(DEFAULT_MCP_URL)
    market_agent = MarketIntelligenceAgent(mcp)
    server = A2AServer(
        agent=market_agent,
        agent_card_path=Path("agents/market/agent_card.json"),
        host="127.0.0.1",
        port=9001,
    )
    server.start_background()

    try:
        await wait_for_server(MARKET_A2A_URL)
        client = A2AClient()

        print("\nDiscovered over HTTP:")
        card = await client.discover(MARKET_A2A_URL)
        print(json.dumps(card, indent=2))

        task = "What's the current price of AAPL?"
        print(f"\nSending A2A task: {task}")
        response = await client.send_task(MARKET_A2A_URL, task)

        print("\nA2A task response:")
        print(json.dumps(response, indent=2))
    finally:
        server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
