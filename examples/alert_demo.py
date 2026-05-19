"""Phase 9 demo: run alert checks once."""

from __future__ import annotations

import asyncio
import json
import sys

from agents.guardian.agent import GuardianAgent
from memory.episodic import EpisodicMemory
from protocols.mcp.client import McpClient
from services.alert_defaults import default_alert_rules
from services.alert_watch import format_alert
from services.alerts import AlertEngine


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Alert Demo (Phase 9)")
    print("Prerequisites: MCP market :8001, MCP EDGAR :8002, Ollama running")
    print("-" * 80)

    memory = EpisodicMemory()
    engine = AlertEngine(
        synthesis_agent=None,
        episodic_memory=memory,
        guardian=GuardianAgent(),
        mcp_client={
            "market": McpClient("http://localhost:8001", timeout=90.0),
            "edgar": McpClient("http://localhost:8002", timeout=120.0),
        },
    )
    for rule in default_alert_rules():
        engine.add_rule(rule)

    print("Registered rules:")
    print(json.dumps([rule.__dict__ for rule in engine.list_rules()], indent=2))

    alerts = await engine.check_all_rules()
    if not alerts:
        print("\nNo alerts triggered.")
        return

    for alert in alerts:
        print(format_alert(alert))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
