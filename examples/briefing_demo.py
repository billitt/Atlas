"""Phase 8 demo: generate one scheduled-style briefing immediately."""

from __future__ import annotations

import asyncio
import sys

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from examples._demo_infra import (
    DEFAULT_AGENT_CARD_URLS,
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from memory.episodic import EpisodicMemory
from protocols.a2a.discovery import load_cards
from services.briefing import BriefingEngine
from services.briefing_templates import format_daily_briefing, format_summary_line


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Briefing Demo (Phase 8)")
    print("Prerequisites: Ollama running, MCP market :8001, MCP EDGAR :8002")
    print("This default watchlist run may take several minutes.")
    print("-" * 80)

    await start_mcp_check()
    servers = start_agent_servers()
    try:
        await wait_for_agent_cards(DEFAULT_AGENT_CARD_URLS)
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
