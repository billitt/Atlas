"""Phase 2 demo — Market Intelligence Agent: query → MCP → Granite → reflect."""

from __future__ import annotations

import asyncio
import json
import sys

from agents.market.agent import DEFAULT_MCP_URL, MarketIntelligenceAgent
from protocols.mcp.client import McpClient


async def run() -> None:
    # Windows consoles default to cp1252; Granite may emit Unicode punctuation in quotes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = "What's happening with TSMC stock today?"

    print("Atlas Market Intelligence Agent (Phase 2 PoC)")
    print(f"Query: {query}")
    print(f"MCP server: {DEFAULT_MCP_URL} (start with: cargo run -p mcp-market-data)")
    print("-" * 60)

    mcp = McpClient(DEFAULT_MCP_URL)
    agent = MarketIntelligenceAgent(mcp)
    await agent.setup()

    result = await agent.run(query)

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"\nConfidence: {result['confidence']}\n")
    print("Analysis:")
    print(result["analysis"])
    print("\nSources:")
    print(json.dumps(result["sources"], indent=2))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
