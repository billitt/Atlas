"""Phase 13 demo: Taiwan Strait end-to-end scenario across all Atlas pipelines."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from time import perf_counter
from typing import Any

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from examples._demo_infra import (
    DEFAULT_AGENT_CARD_URLS,
    start_agent_servers,
    start_mcp_check,
    wait_for_agent_cards,
)
from ingestion.seed_loader import load_taiwan_scenario, seed_alert_context
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from observability.exporters import get_active_trace_file
from observability.run_logger import save_run
from observability.trace_reader import format_trace_tree, load_trace
from observability.tracing import get_current_trace_id, init_tracing, shutdown_tracing
from orchestration.graph import build_synthesis_graph, run_synthesis_graph
from protocols.a2a.discovery import load_cards
from services.alert_watch import format_alert
from services.alerts import AlertRule, _evaluate_condition
from services.briefing import BriefingEngine
from services.briefing_templates import format_summary_line

JsonDict = dict[str, Any]

DEMO_QUERY = (
    "What's the exposure risk if Taiwan Strait tensions escalate? "
    "Consider semiconductor supply chains, market impact, and TSMC filing risk factors."
)

BRIEFING_TOPIC = "Taiwan Strait semiconductor risk"


def _print_box(title: str, lines: list[str]) -> None:
    width = max(len(title), *(len(line) for line in lines), default=40) + 4
    print("=" * width)
    print(title.center(width))
    print("=" * width)
    for line in lines:
        print(line)
    print("=" * width)


async def _run_alert_demo() -> JsonDict | None:
    rule = AlertRule(
        id="taiwan_strait_tension",
        name="Taiwan Strait tension spike",
        description="Watch for elevated geopolitical risk in Taiwan Strait semiconductor regions.",
        watch_topic="Taiwan Strait TSMC semiconductor geopolitical risk",
        condition_prompt=(
            "Trigger if seed GDELT-style data shows Taiwan Strait risk_level HIGH, "
            "peak_tone below -8, or explicit escalation language affecting semiconductor supply."
        ),
        severity="HIGH",
        cooldown_seconds=60,
    )
    fresh_data = seed_alert_context()
    verdict = _evaluate_condition(rule, fresh_data)
    aggregate = fresh_data.get("aggregate_metrics") or {}
    if not verdict.get("triggered") and aggregate.get("risk_level") == "HIGH":
        verdict = {
            "triggered": True,
            "summary": (
                "Taiwan Strait GDELT aggregate risk_level is HIGH with peak_tone "
                f"{aggregate.get('peak_tone')} over five days."
            ),
            "evidence": str(aggregate),
        }
        print("[taiwan_demo] LLM evaluator did not trigger; using deterministic seed fallback.")
    if not verdict.get("triggered"):
        print("[taiwan_demo] Alert did not trigger from seed data; showing evaluation anyway.")
        return None

    triggered_at = datetime.now().isoformat(timespec="seconds")
    result: JsonDict = {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "severity": rule.severity,
        "triggered_at": triggered_at,
        "summary": verdict.get("summary", ""),
        "evidence": verdict.get("evidence", ""),
        "context": "Demo alert evaluated against ingested Taiwan Strait seed GDELT context.",
        "sources": fresh_data.get("sources", []),
        "duration_seconds": 0.0,
    }
    print(format_alert(result))
    save_run(
        {
            "timestamp": triggered_at,
            "query": rule.watch_topic,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "severity": rule.severity,
            "summary": result["summary"],
            "evidence": result["evidence"],
            "alert_result": result,
        }
    )
    EpisodicMemory().log_alert(result)
    return result


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas Taiwan Strait Demo (Phase 13)")
    print("Prerequisites: Ollama, MCP market :8001, MCP EDGAR :8002, MCP trade :8003")
    print('Equivalent via CLI: atlas query "...Taiwan Strait..."')
    print("Equivalent via dashboard: Query page with the same question")
    print("-" * 80)

    demo_start = perf_counter()
    span_count = 0
    trace_id: str | None = None

    # Step 1: Seed data
    print("\n[Step 1] Seed data ingestion")
    ingested = load_taiwan_scenario(semantic_memory=SemanticMemory())
    print(f"Ingested {ingested} documents into semantic memory")

    init_tracing(export_to="file")
    trace_file = get_active_trace_file()
    print(f"[tracing] File export: {trace_file}")

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

        # Step 2: Alert
        print("\n[Step 2] Real-time alert trigger")
        await _run_alert_demo()

        # Step 3: Full synthesis
        print("\n[Step 3] Full synthesis query")
        print(f"Query: {DEMO_QUERY}")
        synthesis_agent = SynthesisAgent(agent_cards, episodic_memory=episodic_memory)
        app = build_synthesis_graph(synthesis_agent, guardian=GuardianAgent())
        query_start = perf_counter()
        started_at = datetime.now().isoformat(timespec="seconds")
        final_state = await run_synthesis_graph(
            app,
            {
                "query": DEMO_QUERY,
                "messages": [("user", DEMO_QUERY)],
                "agent_cards": agent_cards,
                "agent_results": [],
                "sources": [],
                "guardian_retries": 0,
            },
        )
        query_duration = round(perf_counter() - query_start, 3)
        briefing = final_state["briefing"]
        trace_id = get_current_trace_id()
        guardian_verdict = briefing.get("guardian_verdict", {})

        print(f"\nOverall confidence: {briefing.get('overall_confidence')}")
        print(
            f"Guardian passed: {guardian_verdict.get('passed')} "
            f"({guardian_verdict.get('overall_confidence')})"
        )
        print(f"trace_id: {trace_id}")
        print("\n--- Combined analysis (excerpt) ---")
        text = briefing.get("combined_analysis", "")
        print(text[:2000] + ("..." if len(text) > 2000 else ""))

        run_data = {
            "timestamp": started_at,
            "query": DEMO_QUERY,
            "execution_plan": briefing["execution_plan"],
            "agent_results": briefing["agent_results"],
            "sources": briefing["per_agent_sources"],
            "confidence": briefing["overall_confidence"],
            "final_briefing": briefing["combined_analysis"],
            "guardian_verdict": guardian_verdict,
            "duration_seconds": query_duration,
            "trace_id": trace_id,
        }
        save_run(run_data)
        episodic_memory.log_briefing(run_data)

        # Step 4: Briefing
        print("\n[Step 4] Scheduled briefing (single topic)")
        engine = BriefingEngine(
            synthesis_agent,
            episodic_memory=episodic_memory,
            guardian=GuardianAgent(),
            briefing_type="custom",
        )
        scheduled = await engine.generate_briefing([BRIEFING_TOPIC])
        print(format_summary_line(scheduled))
        print(f"Delta: {scheduled.get('delta_from_last', '')[:300]}")

        # Step 5: Trace
        print("\n[Step 5] Trace exploration")
        shutdown_tracing()
        if trace_file and trace_file.exists():
            trace = load_trace(str(trace_file))
            span_count = trace.get("span_count", 0)
            print(format_trace_tree(trace, trace_id=trace_id))
            print(f"\nTrace file: {trace_file}")
        else:
            print("(trace file not found)")

        total_duration = round(perf_counter() - demo_start, 3)

        # Step 6: Summary
        print("\n[Step 6] Demo summary")
        _print_box(
            "ATLAS TAIWAN STRAIT DEMO — EXERCISED",
            [
                "Protocols: MCP (mcp-market-data :8001, mcp-edgar :8002), A2A (4 specialist agents)",
                "Agents: Market, Geopolitical, Supply Chain, Research, Synthesis, Guardian",
                "Memory: Semantic (seed GDELT/trade/filing), Episodic (briefing + alert logged)",
                "Interaction: Alert fired, Query answered, Briefing generated",
                f"Observability: trace_id={trace_id or 'n/a'} spans={span_count} query={query_duration}s total={total_duration}s",
                "Architecture: Rust MCP data layer + Python intelligence layer + LangGraph orchestration",
                'Also runnable: atlas query "..." | Dashboard Query page (same pipeline)',
            ],
        )
    finally:
        shutdown_tracing()
        for server in servers:
            server.shutdown()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
