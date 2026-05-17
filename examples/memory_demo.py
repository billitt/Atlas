"""Phase 5 demo: exercise semantic, episodic, and working memory."""

from __future__ import annotations

from datetime import datetime, timedelta

from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.working import WorkingMemory


def main() -> None:
    print("Atlas Memory Demo (Phase 5)")
    print("-" * 60)

    semantic = SemanticMemory(collection_name="atlas_memory_demo")
    sample_text = (
        "TSMC is a critical semiconductor manufacturer headquartered in Taiwan. "
        "Its advanced foundry capacity is central to global AI accelerator, smartphone, "
        "and high-performance computing supply chains. Taiwan Strait disruptions could "
        "therefore affect chip availability, pricing, and downstream electronics production."
    )
    semantic.add_documents(
        texts=[sample_text],
        metadatas=[{"source": "memory_demo", "topic": "tsmc_supply_chain"}],
        ids=["tsmc_supply_chain_note"],
    )
    semantic_matches = semantic.query("TSMC semiconductor supply chain risk", n_results=3)
    print(f"Semantic memory count: {semantic.count()}")
    print("Semantic query results:")
    for match in semantic_matches:
        print(f"  - distance={match['distance']} metadata={match['metadata']}")
        print(f"    {match['text'][:180]}...")

    episodic = EpisodicMemory()
    fake_run = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "query": "Fake briefing: Taiwan Strait semiconductor exposure",
        "execution_plan": {"steps": [{"agent": "market", "task": "fake task", "depends_on": []}]},
        "agent_results": [{"agent": "market", "confidence": "HIGH"}],
        "final_briefing": "Fake briefing stored for episodic memory demonstration.",
        "confidence": "MEDIUM",
        "sources": [{"type": "demo", "note": "fake memory demo source"}],
        "trace_id": "memory-demo",
        "duration_seconds": 0.01,
    }
    record = episodic.log_briefing(fake_run)
    print(f"\nLogged episodic briefing id: {record.id}")
    recent = episodic.query_briefings("Taiwan semiconductor", limit=5)
    print("Recent episodic briefing matches:")
    for briefing in recent:
        print(f"  - id={briefing.id} confidence={briefing.confidence} query={briefing.query}")

    start = datetime.now() - timedelta(days=1)
    end = datetime.now() + timedelta(days=1)
    in_range = episodic.query_briefings_by_date(start, end)
    print(f"Briefings in +/-1 day range: {len(in_range)}")
    print(f"Confidence history: {episodic.get_confidence_history('Taiwan', days=90)}")

    working = WorkingMemory()
    working.add("query", "How exposed is TSMC?")
    working.add("semantic_matches", semantic_matches[:1])
    working.add("episodic_matches", [briefing.id for briefing in recent])
    print("\nWorking memory context:")
    print(working.to_context_string())
    working.clear()
    print(f"Working memory after clear: {working.get_all()}")


if __name__ == "__main__":
    main()