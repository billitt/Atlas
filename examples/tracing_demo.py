"""Phase 10 demo: OpenTelemetry tracing over the full synthesis pipeline."""

from __future__ import annotations

import asyncio
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
from observability.exporters import get_active_trace_file
from observability.run_logger import save_run
from observability.trace_reader import format_trace_tree, load_trace
from observability.tracing import get_current_trace_id, init_tracing, shutdown_tracing
from orchestration.graph import build_synthesis_graph, run_synthesis_graph
from protocols.a2a.discovery import load_cards


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = (
        "What's the exposure risk if Taiwan Strait tensions escalate? "
        "Consider semiconductor supply chains and market impact."
    )

    print("Atlas Tracing Demo (Phase 10)")
    print("Prerequisites: Ollama running, MCP market :8001, MCP EDGAR :8002, MCP trade :8003")
    print(f"Query: {query}")
    print("-" * 80)

    init_tracing(export_to="file")
    trace_file = get_active_trace_file()
    print(f"[tracing] File export enabled: {trace_file}")

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
        app = build_synthesis_graph(synthesis_agent, guardian=GuardianAgent())

        started_at = datetime.now().isoformat(timespec="seconds")
        start_time = perf_counter()
        final_state = await run_synthesis_graph(
            app,
            {
                "query": query,
                "messages": [("user", query)],
                "agent_cards": agent_cards,
                "agent_results": [],
                "sources": [],
                "guardian_retries": 0,
            },
        )
        duration_seconds = round(perf_counter() - start_time, 3)
        briefing = final_state["briefing"]
        trace_id = get_current_trace_id()

        run_data = {
            "timestamp": started_at,
            "query": query,
            "execution_plan": briefing["execution_plan"],
            "agent_results": briefing["agent_results"],
            "sources": briefing["per_agent_sources"],
            "confidence": briefing["overall_confidence"],
            "final_briefing": briefing["combined_analysis"],
            "guardian_verdict": briefing.get("guardian_verdict", {}),
            "duration_seconds": duration_seconds,
            "trace_id": trace_id,
        }
        save_run(run_data)
        episodic_memory.log_briefing(run_data)

        shutdown_tracing()

        print("\n" + "=" * 80)
        print("EXECUTION TRACE")
        print("=" * 80)
        if trace_file and trace_file.exists():
            trace = load_trace(str(trace_file))
            print(format_trace_tree(trace))
            print(f"\nTrace file: {trace_file}")
        else:
            print("(trace file not found)")
        if trace_id:
            print(f"trace_id: {trace_id} (links run log in runs/ to OTel trace)")
    finally:
        shutdown_tracing()
        for server in servers:
            server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
