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
        **{k: v for k, v in run_data.items() if v is not None},
    }

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[run_logger] Saved run to {path}")
    return path
