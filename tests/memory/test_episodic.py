"""Boundary tests for episodic memory audit trail integrity."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from memory.episodic import BriefingRecord, EpisodicMemory


def test_log_briefing_roundtrip(episodic_db: EpisodicMemory) -> None:
    run_data = {
        "timestamp": datetime(2026, 5, 15, 10, 30, 0),
        "query": "Taiwan semiconductor exposure",
        "briefing_type": "daily",
        "topics": ["Taiwan Strait", "TSMC"],
        "execution_plan": {"steps": [{"agent": "market", "task": "quote TSM"}]},
        "agent_results": [{"agent": "market", "analysis": "TSM up 1.2%"}],
        "final_briefing": "Risk remains elevated for Taiwan supply chain.",
        "confidence": "MEDIUM",
        "sources": [{"symbol": "TSM", "regular_market_price": 145.0}],
        "delta_from_last": "Confidence unchanged since last briefing.",
        "trace_id": "trace-abc-123",
        "duration_seconds": 42.5,
        "guardian_verdict": {"passed": True, "overall_confidence": "MEDIUM"},
    }

    record = episodic_db.log_briefing(run_data)

    with Session(episodic_db.engine) as session:
        stored = session.get(BriefingRecord, record.id)
        assert stored is not None
        assert stored.query == run_data["query"]
        assert stored.briefing_type == "daily"
        assert stored.topics == ["Taiwan Strait", "TSMC"]
        assert stored.plan == run_data["execution_plan"]
        assert stored.final_briefing == run_data["final_briefing"]
        assert stored.confidence == "MEDIUM"
        assert stored.sources == run_data["sources"]
        assert stored.delta_from_last == run_data["delta_from_last"]
        assert stored.trace_id == "trace-abc-123"
        assert stored.duration_seconds == 42.5


def test_log_briefing_preserves_guardian_in_agent_results(episodic_db: EpisodicMemory) -> None:
    guardian_verdict = {
        "passed": False,
        "overall_confidence": "LOW",
        "summary": "Unsupported revenue claim flagged.",
    }
    record = episodic_db.log_briefing(
        {
            "query": "TSMC revenue check",
            "final_briefing": "Draft briefing",
            "confidence": "LOW",
            "agent_results": [{"agent": "market", "analysis": "draft"}],
            "guardian_verdict": guardian_verdict,
        }
    )

    guardian_entries = [
        item for item in record.agent_results if item.get("agent") == "guardian"
    ]
    assert len(guardian_entries) == 1
    assert guardian_entries[0]["verdict"] == guardian_verdict


def test_query_briefings_by_date_range(episodic_db: EpisodicMemory) -> None:
    dates = [
        datetime(2026, 5, 10, 9, 0, 0),
        datetime(2026, 5, 15, 9, 0, 0),
        datetime(2026, 5, 20, 9, 0, 0),
    ]
    for index, timestamp in enumerate(dates):
        episodic_db.log_briefing(
            {
                "timestamp": timestamp,
                "query": f"topic-{index}",
                "final_briefing": f"briefing-{index}",
                "confidence": "MEDIUM",
            }
        )

    results = episodic_db.query_briefings_by_date(
        datetime(2026, 5, 14, 0, 0, 0),
        datetime(2026, 5, 18, 23, 59, 59),
    )

    assert len(results) == 1
    assert results[0].query == "topic-1"

    with Session(episodic_db.engine) as session:
        all_records = list(
            session.exec(select(BriefingRecord).order_by(BriefingRecord.timestamp.desc()))
        )
    assert len(all_records) == 3
