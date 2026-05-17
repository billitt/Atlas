"""Placeholder Geopolitical Agent for Phase 3 A2A discovery demos."""

from __future__ import annotations

from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence


class GeopoliticalRiskAgent(BaseAgent):
    """Stub specialist agent.

    Phase 3 needs an Agent Card and callable placeholder so discovery can prove
    multiple agents can exist. Real geopolitical data sources arrive in later phases.
    """

    async def plan(self, query: str) -> dict[str, Any]:
        print("[geopolitical.plan] Placeholder plan")
        return {"query": query, "data_sources": []}

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        print("[geopolitical.execute] Returning canned placeholder response")
        return {
            "analysis": (
                "Geopolitical Risk Agent placeholder: real event ingestion is not "
                f"implemented yet. Received task: {query}"
            ),
            "sources": [
                {
                    "type": "placeholder",
                    "agent": "geopolitical",
                    "note": "Phase 3 card/server stub only",
                }
            ],
            "confidence": "LOW",
        }

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        print("[geopolitical.reflect] Placeholder reflection")
        return True, "Placeholder response is explicitly labeled as not implemented.", "LOW"
