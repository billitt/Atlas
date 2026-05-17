"""Supply Chain Agent.

This Phase 4 version uses Granite model knowledge only. Real port, trade, and
supplier graph MCP data arrives later, so the agent must disclose its limits.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence
from services.llm import chat


class SupplyChainAgent(BaseAgent):
    """Specialist agent for supply chain risk and dependency reasoning."""

    async def plan(self, query: str) -> dict[str, Any]:
        print("[supply_chain.plan] Identifying supply-chain dimensions...")
        prompt = f"""You are the Atlas Supply Chain Agent in the PLAN phase.
Create a concise plan for supply-chain analysis.

Query: {query}

Important limitation:
- No live supplier graph, port, tariff, or trade MCP data is available yet.
- Your analysis must rely on model knowledge and disclose that limitation.

Return ONLY valid JSON:
{{
  "supply_chain_dimensions": ["critical inputs", "shipping chokepoints", "substitution risk"],
  "entities": ["companies, regions, commodities, components"],
  "rationale": "why these dimensions matter"
}}
"""
        raw = chat(prompt)
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return {
                "supply_chain_dimensions": ["critical inputs", "logistics chokepoints"],
                "entities": [],
                "rationale": "Fallback plan because the model did not return valid JSON.",
            }

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        print("[supply_chain.execute] Drafting model-knowledge supply-chain analysis...")
        prompt = f"""You are the Atlas Supply Chain Agent.
Analyze the supply-chain implications of the query using the plan below.

Query: {query}
Plan:
{json.dumps(plan, indent=2)}

Constraints:
- You do not have live supplier, port, shipping, tariff, or customs MCP data yet.
- Do not invent current disruptions.
- Clearly label the assessment as based on model knowledge, not live data.
- Focus on dependencies, chokepoints, substitution options, lead-time risk, and
  likely second-order impacts.

Return 3-5 concise paragraphs.
"""
        analysis = chat(prompt).strip()
        return {
            "analysis": analysis,
            "sources": [
                {
                    "type": "model_knowledge",
                    "agent": "supply_chain",
                    "note": "Assessment based on Granite model knowledge; live supply-chain MCP data is not implemented yet.",
                    "planned_dimensions": plan.get("supply_chain_dimensions", []),
                }
            ],
            "confidence": "MEDIUM",
        }

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        print("[supply_chain.reflect] Checking limitation disclosure...")
        prompt = f"""You are auditing a supply-chain analysis draft.

Query: {query}

Draft:
{draft["analysis"]}

The draft MUST disclose that it is based on model knowledge, not live supplier,
shipping, tariff, customs, or port data.

Return ONLY valid JSON:
{{
  "passed": true or false,
  "confidence": "MEDIUM" or "LOW",
  "feedback": "short audit note"
}}
"""
        raw = chat(prompt)
        try:
            verdict = _parse_json(raw)
        except json.JSONDecodeError:
            return False, "Reflection did not return valid JSON.", "LOW"

        confidence = str(verdict.get("confidence", "LOW")).upper()
        if confidence not in {"MEDIUM", "LOW"}:
            confidence = "LOW"
        return bool(verdict.get("passed")), str(verdict.get("feedback", "")), confidence  # type: ignore[return-value]


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
