"""Geopolitical Risk Agent.

Phase 4 gives this agent real reasoning behavior, but it is still intentionally
limited: no geopolitical MCP server exists yet, so every answer must disclose
that it is based on Granite model knowledge rather than live event data.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence, normalize_confidence, parse_json_from_llm
from agents.formatting import MARKDOWN_FORMAT_INSTRUCTIONS
from memory.semantic import SemanticMemory
from services.llm import chat


class GeopoliticalRiskAgent(BaseAgent):
    """Specialist agent for geopolitical risk, pending live MCP data sources."""

    def __init__(
        self,
        *,
        max_retries: int = 2,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.semantic_memory = semantic_memory or SemanticMemory()

    async def plan(self, query: str) -> dict[str, Any]:
        print("[geopolitical.plan] Identifying risk dimensions...")
        prompt = f"""You are the Atlas Geopolitical Risk Agent in the PLAN phase.
Create a concise analysis plan for this query.

Query: {query}

Important limitation:
- No live geopolitical MCP data source is available yet.
- Your analysis must rely on model knowledge and must disclose that limitation.

Return ONLY valid JSON:
{{
  "risk_dimensions": ["military escalation", "sanctions", "trade disruption"],
  "entities": ["countries, companies, regions, or assets involved"],
  "rationale": "why these dimensions matter"
}}
"""
        raw = chat(prompt)
        try:
            return parse_json_from_llm(raw)
        except json.JSONDecodeError:
            return {
                "risk_dimensions": ["geopolitical escalation", "trade disruption"],
                "entities": [],
                "rationale": "Fallback plan because the model did not return valid JSON.",
            }

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        print("[geopolitical.execute] Drafting risk assessment...")
        semantic_context, semantic_sources = self._semantic_context(query)
        has_seed = bool(semantic_sources)
        data_label = (
            "semantic memory seed context (simulated GDELT-style events)"
            if has_seed
            else "model knowledge only (no live geopolitical MCP feed)"
        )
        prompt = f"""You are the Atlas Geopolitical Risk Agent.
Assess the geopolitical risks relevant to the query using the plan below.

Query: {query}
Plan:
{json.dumps(plan, indent=2)}

Relevant semantic memory context:
{semantic_context}

Constraints:
- Base claims on the semantic memory context when provided; do not invent events beyond it.
- If no seed context is available, rely on model knowledge and disclose that limitation.
- Clearly state whether the assessment uses seed GDELT-style context or model knowledge only.
- Focus on escalation paths, trade exposure, chokepoints, sanctions/export controls,
  and second-order market or supply-chain effects.

{MARKDOWN_FORMAT_INSTRUCTIONS}
"""
        analysis = chat(prompt).strip()
        sources: list[dict[str, Any]] = list(semantic_sources)
        if not sources:
            sources.append(
                {
                    "type": "model_knowledge",
                    "agent": "geopolitical",
                    "note": "Assessment based on Granite model knowledge; live geopolitical MCP data is not implemented yet.",
                    "planned_dimensions": plan.get("risk_dimensions", []),
                }
            )
        else:
            sources.append(
                {
                    "type": "semantic_memory",
                    "agent": "geopolitical",
                    "note": f"Grounded in semantic memory ({data_label}).",
                    "planned_dimensions": plan.get("risk_dimensions", []),
                }
            )
        return {
            "analysis": analysis,
            "sources": sources,
            "confidence": "MEDIUM" if has_seed else "MEDIUM",
        }

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        print("[geopolitical.reflect] Checking limitation disclosure...")
        prompt = f"""You are auditing a geopolitical risk draft.

Query: {query}

Draft:
{draft["analysis"]}

If semantic memory seed context was used, claims should trace to that context.
If only model knowledge was used, the draft MUST disclose that limitation.
It should avoid claiming current breaking events unless supported by provided context.

Return ONLY valid JSON:
{{
  "passed": true or false,
  "confidence": "MEDIUM" or "LOW",
  "feedback": "short audit note"
}}
"""
        raw = chat(prompt)
        try:
            verdict = parse_json_from_llm(raw)
        except json.JSONDecodeError:
            return False, "Reflection did not return valid JSON.", "LOW"

        confidence = normalize_confidence(verdict.get("confidence", "LOW"))
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
            if metadata.get("category") == "geopolitical" or metadata.get("source") == "seed_gdelt":
                sources.append(
                    {"type": "semantic_memory", **metadata, "excerpt": match.get("text", "")[:400]}
                )
            lines.append(
                f"- {match['text']}\n  metadata={metadata} distance={match.get('distance')}"
            )
        return "\n\n".join(lines), sources
