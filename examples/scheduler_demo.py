"""Phase 8 demo: autonomous scheduled briefings."""

from __future__ import annotations

import asyncio
import sys

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from examples.briefing_demo import start_agent_servers, wait_for_agent_cards
from memory.episodic import EpisodicMemory
from protocols.a2a.discovery import load_cards
from services.briefing import BriefingEngine
from services.scheduler import AtlasScheduler


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Scheduler Demo (Phase 8)")
    print("Schedules a custom briefing every 60 seconds and stops after 3 minutes.")
    print("Prerequisites: Ollama running, MCP market :8001, MCP EDGAR :8002")
    print("-" * 80)

    servers = start_agent_servers()
    scheduler: AtlasScheduler | None = None
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
            briefing_type="custom",
        )
        scheduler = AtlasScheduler(engine)
        scheduler.start()
        scheduler.schedule_custom(
            "*/1 * * * *",
            ["semiconductor supply chain"],
        )
        print("Scheduled jobs:")
        for job in scheduler.list_jobs():
            print(f"  - {job['id']} next={job['next_run_time']}")
        await asyncio.sleep(185)
    finally:
        if scheduler is not None:
            scheduler.stop()
        for server in servers:
            server.shutdown()
        print("[scheduler_demo] Shutdown complete")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
