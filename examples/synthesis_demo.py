"""Phase 4 demo: multi-agent synthesis over A2A + LangGraph."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from time import perf_counter

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from examples._demo_infra import (
    DEFAULT_AGENT_CARD_URLS,
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.working import WorkingMemory
from observability.run_logger import save_run
from orchestration.graph import build_synthesis_graph
from protocols.a2a.discovery import load_cards


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = (
        "What's the exposure risk if Taiwan Strait tensions escalate? "
        "Consider semiconductor supply chains and market impact."
    )

    print("Atlas Synthesis Demo (Phase 4)")
    print("Prerequisites: Ollama running, MCP market :8001, MCP EDGAR :8002")
    print(f"Query: {query}")
    print("-" * 80)

    await start_mcp_check()
    servers = start_agent_servers()

    try:
        await wait_for_agent_cards(DEFAULT_AGENT_CARD_URLS)

        registry = load_cards("agents")
        discovered_cards = registry.discover_all()
        agent_cards = [
            card for card in discovered_cards if "guardian" not in str(card.get("name", "")).lower()
        ]
        episodic_memory = EpisodicMemory()
        semantic_memory = SemanticMemory()
        working_memory = WorkingMemory()
        working_memory.add("query", query)
        working_memory.add("agent_card_count", len(discovered_cards))
        print("Discovered local Agent Cards:")
        for card in discovered_cards:
            skills = ", ".join(skill["id"] for skill in card.get("skills", []))
            print(f"  - {card['name']} at {card['url']} [{skills}]")
        print("Guardian runs as an in-graph validator, not as a specialist delegate.")

        synthesis_agent = SynthesisAgent(agent_cards, episodic_memory=episodic_memory)
        app = build_synthesis_graph(synthesis_agent, guardian=GuardianAgent())

        started_at = datetime.now().isoformat(timespec="seconds")
        start_time = perf_counter()
        final_state = await app.ainvoke(
            {
                "query": query,
                "messages": [("user", query)],
                "agent_cards": agent_cards,
                "agent_results": [],
                "sources": [],
                "guardian_retries": 0,
            }
        )
        duration_seconds = round(perf_counter() - start_time, 3)
        briefing = final_state["briefing"]
        working_memory.add("execution_plan", briefing["execution_plan"])
        working_memory.add("overall_confidence", briefing["overall_confidence"])

        print("\n" + "=" * 80)
        print("SYNTHESIZED BRIEFING")
        print("=" * 80)
        print(f"\nOverall confidence: {briefing['overall_confidence']}\n")
        print(briefing["combined_analysis"])

        print("\nExecution plan:")
        print(json.dumps(briefing["execution_plan"], indent=2))

        print("\nPer-agent sources:")
        print(json.dumps(briefing["per_agent_sources"], indent=2))

        guardian_verdict = briefing.get("guardian_verdict", {})
        print("\nGuardian validation:")
        print(f"  Overall confidence: {guardian_verdict.get('overall_confidence', 'LOW')}")
        print(f"  Passed: {guardian_verdict.get('passed', False)}")
        flags = guardian_verdict.get("flags", [])
        if flags:
            print("  Flags:")
            for flag in flags:
                print(f"    - {flag}")
        claim_checks = guardian_verdict.get("claim_checks", [])
        if claim_checks:
            print("  Claim checks:")
            for check in claim_checks[:8]:
                status = "PASS" if check.get("grounded") else "FLAG"
                print(f"    - {status} [{check.get('confidence')}]: {check.get('claim')}")
                if check.get("issue"):
                    print(f"      issue: {check.get('issue')}")

        run_data = {
            "timestamp": started_at,
            "query": query,
            "execution_plan": briefing["execution_plan"],
            "agent_results": briefing["agent_results"],
            "sources": briefing["per_agent_sources"],
            "confidence": briefing["overall_confidence"],
            "final_briefing": briefing["combined_analysis"],
            "guardian_verdict": guardian_verdict,
            "duration_seconds": duration_seconds,
            "memory_stats": {
                "semantic_docs": semantic_memory.count(),
                "episodic_briefings": episodic_memory.briefing_count(),
                "working_memory_keys": list(working_memory.get_all().keys()),
            },
        }
        save_run(run_data)
        episodic_memory.log_briefing(run_data)
        print(
            "[memory] Persisted run to JSON and SQLite "
            f"(semantic_docs={run_data['memory_stats']['semantic_docs']}, "
            f"episodic_briefings={episodic_memory.briefing_count()}, "
            f"working_keys={run_data['memory_stats']['working_memory_keys']})"
        )
        working_memory.clear()
    finally:
        for server in servers:
            server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
