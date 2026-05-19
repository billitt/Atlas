"""Phase 9 demo: run the alert watch loop briefly."""

from __future__ import annotations

import asyncio
import sys

from agents.guardian.agent import GuardianAgent
from memory.episodic import EpisodicMemory
from protocols.mcp.client import McpClient
from services.alert_defaults import default_alert_rules
from services.alert_watch import AlertWatcher
from services.alerts import AlertEngine


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Alert Watch Demo (Phase 9)")
    print("Runs a lightweight watch loop every 60 seconds for 3 minutes.")
    print("Prerequisites: MCP market :8001, MCP EDGAR :8002, Ollama running")
    print("-" * 80)

    engine = AlertEngine(
        synthesis_agent=None,
        episodic_memory=EpisodicMemory(),
        guardian=GuardianAgent(),
        mcp_client={
            "market": McpClient("http://localhost:8001", timeout=90.0),
            "edgar": McpClient("http://localhost:8002", timeout=120.0),
        },
    )
    for rule in default_alert_rules()[:2]:
        engine.add_rule(rule)

    watcher = AlertWatcher(engine, check_interval_seconds=60)
    task = asyncio.create_task(watcher.start())
    try:
        await asyncio.sleep(180)
    finally:
        watcher.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("[alert_watch_demo] Watch task cancelled cleanly")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
