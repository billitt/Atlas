"""Supply Chain Agent.

This Phase 4 version uses Granite model knowledge only. Real port, trade, and
supplier graph MCP data arrives later, so the agent must disclose its limits.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence
from memory.semantic import SemanticMemory
from services.llm import chat


class SupplyChainAgent(BaseAgent):
    """Specialist agent for supply chain risk and dependency reasoning."""

    def __init__(
        self,
        *,
        max_retries: int = 2,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.semantic_memory = semantic_memory or SemanticMemory()

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
        print("[supply_chain.execute] Drafting supply-chain analysis...")
        semantic_context, semantic_sources = self._semantic_context(query)
        prompt = f"""You are the Atlas Supply Chain Agent.
Analyze the supply-chain implications of the query using the plan below.

Query: {query}
Plan:
{json.dumps(plan, indent=2)}

Relevant semantic memory context:
{semantic_context}

Constraints:
- Base claims on semantic memory trade-flow and chokepoint data when provided.
- If no seed context is available, rely on model knowledge and disclose that limitation.
- Clearly state whether the assessment uses seed trade data or model knowledge only.
- Focus on dependencies, chokepoints, substitution options, lead-time risk, and
  likely second-order impacts.

Return 3-5 concise paragraphs.
"""
        analysis = chat(prompt).strip()
        sources: list[dict[str, Any]] = list(semantic_sources)
        if not sources:
            sources.append(
                {
                    "type": "model_knowledge",
                    "agent": "supply_chain",
                    "note": "Assessment based on Granite model knowledge; live supply-chain MCP data is not implemented yet.",
                    "planned_dimensions": plan.get("supply_chain_dimensions", []),
                }
            )
        else:
            sources.append(
                {
                    "type": "semantic_memory",
                    "agent": "supply_chain",
                    "note": "Grounded in semantic memory (simulated UN Comtrade-style trade flow data).",
                    "planned_dimensions": plan.get("supply_chain_dimensions", []),
                }
            )
        return {
            "analysis": analysis,
            "sources": sources,
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

If semantic memory trade-flow context was used, claims should trace to that context.
If only model knowledge was used, the draft MUST disclose that limitation.

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

    def _semantic_context(self, query: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            if self.semantic_memory.count() == 0:
                return "(no semantic memory documents stored)", []
            matches = self.semantic_memory.query(query, n_results=5)
        except Exception as exc:
            return f"(semantic memory unavailable: {exc})", []

        if not matches:
            return "(no relevant semantic memory matches)", []

        sources: list[dict[str, Any]] = []
        lines: list[str] = []
        for match in matches:
            metadata = match.get("metadata") or {}
            if (
                metadata.get("category") == "supply_chain"
                or metadata.get("source") == "seed_comtrade"
            ):
                sources.append(
                    {"type": "semantic_memory", **metadata, "excerpt": match.get("text", "")[:400]}
                )
            lines.append(
                f"- {match['text']}\n  metadata={metadata} distance={match.get('distance')}"
            )
        return "\n\n".join(lines), sources


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
