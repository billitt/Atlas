"""Simple runtime artifact logger for Atlas demos."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def save_run(run_data: dict[str, Any]) -> Path:
    """Persist one run record to `runs/YYYYMMDD_HHMMSS.json`."""
    runs_dir = Path("runs")
    runs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = run_data.get("timestamp") or datetime.now().isoformat(timespec="seconds")
    safe_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = runs_dir / f"{safe_timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "query": run_data.get("query"),
        "briefing_type": run_data.get("briefing_type"),
        "topics": run_data.get("topics", []),
        "sections_count": run_data.get("sections_count"),
        "overall_risk_level": run_data.get("overall_risk_level"),
        "execution_plan": run_data.get("execution_plan"),
        "agent_results": run_data.get("agent_results"),
        "sources": run_data.get("sources"),
        "confidence": run_data.get("confidence"),
        "final_briefing": run_data.get("final_briefing"),
        "guardian_verdict": run_data.get("guardian_verdict", {}),
        "delta_from_last": run_data.get("delta_from_last"),
        "per_topic": run_data.get("per_topic", []),
        "duration_seconds": run_data.get("duration_seconds"),
        "memory_stats": run_data.get("memory_stats", {}),
    }

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[run_logger] Saved run to {path}")
    return path
