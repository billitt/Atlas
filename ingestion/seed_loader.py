"""Load Taiwan Strait demo seed data into semantic memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory.semantic import SemanticMemory

JsonDict = dict[str, Any]

SEED_DIR = Path("data/seed_data")
SCENARIO_NAME = "taiwan_strait_escalation"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _scenario_documents() -> tuple[list[str], list[JsonDict], list[str]]:
    """Build document texts, metadatas, and ids for Taiwan scenario seed files."""
    texts: list[str] = []
    metadatas: list[JsonDict] = []
    ids: list[str] = []

    scenario_path = SEED_DIR / "taiwan_scenario.json"
    scenario = json.loads(_read_text(scenario_path))
    for index, event in enumerate(scenario.get("events") or []):
        body = (
            f"GDELT-style conflict event ({event.get('date')}) in {event.get('region')}.\n"
            f"Tone: {event.get('gldelt_tone')} | Goldstein: {event.get('goldstein_scale')}\n"
            f"Entities: {', '.join(event.get('entities') or [])}\n"
            f"Summary: {event.get('summary')}"
        )
        texts.append(body)
        metadatas.append(
            {
                "source": "seed_gdelt",
                "date": event.get("date"),
                "category": "geopolitical",
                "scenario_name": SCENARIO_NAME,
                "region": event.get("region"),
            }
        )
        ids.append(f"taiwan-gdelt-{index}")

    aggregate = scenario.get("aggregate_metrics") or {}
    texts.append(
        "Taiwan Strait 5-day GDELT aggregate:\n"
        f"avg_tone={aggregate.get('five_day_avg_tone')} peak_tone={aggregate.get('peak_tone')} "
        f"risk_level={aggregate.get('risk_level')} sectors={aggregate.get('affected_sectors')}"
    )
    metadatas.append(
        {
            "source": "seed_gdelt",
            "date": "2026-05-27",
            "category": "geopolitical",
            "scenario_name": SCENARIO_NAME,
            "region": "Taiwan Strait",
        }
    )
    ids.append("taiwan-gdelt-aggregate")

    filing_path = SEED_DIR / "tsmc_filing_excerpt.txt"
    texts.append(_read_text(filing_path))
    metadatas.append(
        {
            "source": "seed_sec_filing",
            "date": "2026-05-27",
            "category": "filing",
            "scenario_name": SCENARIO_NAME,
            "ticker": "TSM",
        }
    )
    ids.append("taiwan-tsmc-filing-excerpt")

    trade_path = SEED_DIR / "trade_flow_data.json"
    trade = json.loads(_read_text(trade_path))
    texts.append(json.dumps(trade, indent=2))
    metadatas.append(
        {
            "source": "seed_comtrade",
            "date": "2026-05-27",
            "category": "supply_chain",
            "scenario_name": SCENARIO_NAME,
        }
    )
    ids.append("taiwan-trade-flow")

    for index, choke in enumerate(trade.get("chokepoints") or []):
        body = (
            f"Supply chain chokepoint: {choke.get('name')}\n"
            f"Share/role: {choke.get('share_of_global_advanced_chips_percent') or choke.get('role')}\n"
            f"Impact: {choke.get('impact_if_disrupted')}"
        )
        texts.append(body)
        metadatas.append(
            {
                "source": "seed_comtrade",
                "date": "2026-05-27",
                "category": "supply_chain",
                "scenario_name": SCENARIO_NAME,
            }
        )
        ids.append(f"taiwan-chokepoint-{index}")

    return texts, metadatas, ids


def load_taiwan_scenario(
    *,
    semantic_memory: SemanticMemory | None = None,
    persist_dir: str = "data/chroma",
) -> int:
    """Ingest Taiwan Strait demo seed files into semantic memory. Returns document count."""
    memory = semantic_memory or SemanticMemory(persist_dir=persist_dir)
    texts, metadatas, ids = _scenario_documents()
    memory.add_documents(texts, metadatas, ids)
    count = memory.count()
    print(
        f"[seed_loader] Ingested {len(texts)} seed documents ({count} total chunks in semantic memory)"
    )
    return len(texts)


def seed_alert_context() -> JsonDict:
    """Return fresh-data-shaped payload from seed files for demo alert evaluation."""
    scenario = json.loads(_read_text(SEED_DIR / "taiwan_scenario.json"))
    trade = json.loads(_read_text(SEED_DIR / "trade_flow_data.json"))
    return {
        "type": "geopolitical_seed",
        "scenario_name": SCENARIO_NAME,
        "aggregate_metrics": scenario.get("aggregate_metrics"),
        "events": scenario.get("events"),
        "trade_dependency_summary": trade.get("dependency_summary"),
        "sources": [
            {"source": "seed_gdelt", "path": str(SEED_DIR / "taiwan_scenario.json")},
            {"source": "seed_comtrade", "path": str(SEED_DIR / "trade_flow_data.json")},
        ],
    }
