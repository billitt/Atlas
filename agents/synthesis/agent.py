"""Synthesis Agent: orchestrates specialist agents through A2A."""

from __future__ import annotations

import json
from typing import Any

from agents.synthesis.planner import agent_key, create_execution_plan
from protocols.a2a.client import A2AClient
from services.llm import chat

JsonDict = dict[str, Any]


class SynthesisAgent:
    """Cross-domain orchestrator.

    This agent intentionally does not extend BaseAgent. It does not own one
    specialist plan/execute/reflect loop; instead it creates a DAG, delegates to
    multiple A2A agents, and synthesizes their returned artifacts.
    """

    def __init__(self, agent_cards: list[JsonDict], *, a2a_client: A2AClient | None = None) -> None:
        self.agent_cards = agent_cards
        self.a2a = a2a_client or A2AClient(timeout=240.0)
        self.card_by_key = {agent_key(card): card for card in agent_cards}

    def plan(self, query: str) -> JsonDict:
        return create_execution_plan(query, self.agent_cards)

    async def delegate(self, plan: JsonDict) -> list[JsonDict]:
        """Run plan steps sequentially through A2A `tasks/send`.

        Sequential execution is deliberate for now: every specialist may call the
        same local Granite model through Ollama, so parallel calls would contend
        for a single GPU/model runtime.
        """
        results: list[JsonDict] = []
        completed: set[str] = set()

        for index, step in enumerate(plan.get("steps", []), start=1):
            agent = str(step.get("agent"))
            depends_on = set(step.get("depends_on", []))
            missing = depends_on - completed
            if missing:
                raise RuntimeError(f"step {agent} depends on incomplete steps: {sorted(missing)}")

            card = self.card_by_key.get(agent)
            if card is None:
                raise RuntimeError(f"plan referenced unknown agent: {agent}")

            task = str(step.get("task", ""))
            print(f"[synthesis.delegate] Step {index}: {agent} -> {task}")
            response = await self.a2a.send_task(str(card["url"]), task)
            results.append(
                {
                    "agent": agent,
                    "task": task,
                    "card": card,
                    "response": response,
                    "artifact": _first_artifact(response),
                }
            )
            completed.add(agent)

        return results

    def synthesize(self, query: str, plan: JsonDict, agent_results: list[JsonDict]) -> JsonDict:
        """Use Granite to merge specialist outputs into one briefing."""
        compact_results = [_compact_result(result) for result in agent_results]
        prompt = f"""You are the Atlas Synthesis Agent.
Create a unified intelligence briefing from specialist agent outputs.

Original user query:
{query}

Execution plan:
{json.dumps(plan, indent=2)}

Specialist results:
{json.dumps(compact_results, indent=2)}

Instructions:
- Merge the market, geopolitical, and supply-chain perspectives.
- Explicitly call out confidence differences and live-data limitations.
- Resolve conflicts; if no direct conflict exists, say the outputs are complementary.
- Keep the briefing grounded in the specialist artifacts.

Return 4-6 concise paragraphs plus a short "Key sources" line.
"""
        combined_analysis = chat(prompt).strip()
        return {
            "combined_analysis": combined_analysis,
            "per_agent_sources": _collect_sources(agent_results),
            "overall_confidence": _overall_confidence(agent_results),
            "execution_plan": plan,
            "agent_results": compact_results,
        }

    async def run(self, query: str) -> JsonDict:
        plan = self.plan(query)
        results = await self.delegate(plan)
        return self.synthesize(query, plan, results)


def _first_artifact(task_response: JsonDict) -> JsonDict:
    artifacts = task_response.get("artifacts", [])
    if isinstance(artifacts, list) and artifacts:
        first = artifacts[0]
        if isinstance(first, dict):
            return first
    return {}


def _compact_result(result: JsonDict) -> JsonDict:
    metadata = result.get("artifact", {}).get("metadata", {})
    return {
        "agent": result.get("agent"),
        "task": result.get("task"),
        "analysis": metadata.get("analysis"),
        "confidence": metadata.get("confidence"),
        "sources": metadata.get("sources", []),
    }


def _collect_sources(agent_results: list[JsonDict]) -> list[JsonDict]:
    sources: list[JsonDict] = []
    for result in agent_results:
        metadata = result.get("artifact", {}).get("metadata", {})
        for source in metadata.get("sources", []):
            if isinstance(source, dict):
                sources.append({"agent": result.get("agent"), **source})
    return sources


def _overall_confidence(agent_results: list[JsonDict]) -> str:
    ranks = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    confidences: list[str] = []
    for result in agent_results:
        metadata = result.get("artifact", {}).get("metadata", {})
        confidence = str(metadata.get("confidence", "LOW")).upper()
        confidences.append(confidence if confidence in ranks else "LOW")
    if not confidences:
        return "LOW"
    return min(confidences, key=lambda c: ranks[c])
