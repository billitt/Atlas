"""Phase 7 demo: Guardian validation over a fake briefing."""

from __future__ import annotations

import json
import sys

from agents.guardian.agent import GuardianAgent


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = "Assess semiconductor supply-chain exposure."
    briefing = {
        "combined_analysis": (
            "TSMC is central to advanced semiconductor manufacturing, based on the supplied "
            "supply-chain source. Atlas also confirms that a new chip export ban was signed "
            "this morning, which immediately halted all shipments."
        ),
        "overall_confidence": "HIGH",
    }
    agent_results = [
        {
            "agent": "supply_chain",
            "analysis": "TSMC is central to advanced semiconductor manufacturing.",
            "confidence": "MEDIUM",
            "sources": [
                {
                    "title": "Supply-chain agent model-knowledge assessment",
                    "date": "2026-05-17",
                    "text": "TSMC is central to advanced semiconductor manufacturing.",
                }
            ],
        }
    ]
    sources = agent_results[0]["sources"]

    print("Atlas Guardian Demo (Phase 7)")
    print("One claim is grounded; one claim is intentionally fabricated.")
    print("-" * 72)

    verdict = GuardianAgent().validate(query, briefing, agent_results, sources)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
