"""Synthesis Agent: orchestrates specialist agents through A2A."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from agents.formatting import MARKDOWN_FORMAT_INSTRUCTIONS
from agents.synthesis.planner import agent_key, create_execution_plan
from memory.episodic import EpisodicMemory
from protocols.a2a.client import A2AClient
from services.llm import chat
from services.runtime_config import recommended_concurrency

JsonDict = dict[str, Any]


class SynthesisAgent:
    """Cross-domain orchestrator.

    This agent intentionally does not extend BaseAgent. It does not own one
    specialist plan/execute/reflect loop; instead it creates a DAG, delegates to
    multiple A2A agents, and synthesizes their returned artifacts.
    """

    def __init__(
        self,
        agent_cards: list[JsonDict],
        *,
        a2a_client: A2AClient | None = None,
        episodic_memory: EpisodicMemory | None = None,
    ) -> None:
        self.agent_cards = agent_cards
        # 300s headroom: a reflection retry runs two plan→execute→reflect passes,
        # which can exceed lower timeouts on single-GPU hardware
        self.a2a = a2a_client or A2AClient(timeout=300.0)
        self.card_by_key = {agent_key(card): card for card in agent_cards}
        self.episodic_memory = episodic_memory or EpisodicMemory()

    def plan(self, query: str) -> JsonDict:
        return create_execution_plan(query, self.agent_cards)

    async def delegate(
        self,
        plan: JsonDict,
        on_step_done: Callable[[JsonDict], None] | None = None,
    ) -> list[JsonDict]:
        """Run plan steps through A2A `tasks/send`, fanning out independent steps.

        Steps whose `depends_on` are already satisfied run concurrently in
        dependency "waves" via `asyncio.gather`. Concurrency is bounded by an
        `asyncio.Semaphore` sized to the host machine (`recommended_concurrency`)
        so Atlas never fires more simultaneous Granite calls than the hardware
        was sized for. The returned list preserves the original plan order for
        deterministic synthesis input.

        ``on_step_done`` is called synchronously after each step completes,
        allowing callers to stream per-agent progress events.
        """
        steps = list(plan.get("steps", []))

        # Validate agents and dependency references up front.
        known_agents = {str(step.get("agent")) for step in steps}
        for step in steps:
            agent = str(step.get("agent"))
            if self.card_by_key.get(agent) is None:
                raise RuntimeError(f"plan referenced unknown agent: {agent}")
            unknown_deps = set(step.get("depends_on", [])) - known_agents
            if unknown_deps:
                raise RuntimeError(
                    f"step {agent} depends on unknown steps: {sorted(unknown_deps)}"
                )

        semaphore = asyncio.Semaphore(max(1, recommended_concurrency()))

        async def _run_step(step: JsonDict) -> JsonDict:
            agent = str(step.get("agent"))
            card = self.card_by_key[agent]
            task = str(step.get("task", ""))
            async with semaphore:
                print(f"[synthesis.delegate] {agent} -> {task}")
                response = await self.a2a.send_task(str(card["url"]), task)
            result = {
                "agent": agent,
                "task": task,
                "card": card,
                "response": response,
                "artifact": _first_artifact(response),
            }
            if on_step_done is not None:
                on_step_done(result)
            return result

        completed: set[str] = set()
        results_by_agent: dict[str, JsonDict] = {}
        remaining = steps[:]

        while remaining:
            wave = [
                step
                for step in remaining
                if set(step.get("depends_on", [])) <= completed
            ]
            if not wave:
                stuck = [str(step.get("agent")) for step in remaining]
                raise RuntimeError(f"unsatisfiable step dependencies among: {stuck}")

            wave_results = await asyncio.gather(*(_run_step(step) for step in wave))
            for step, result in zip(wave, wave_results):
                agent = str(step.get("agent"))
                results_by_agent[agent] = result
                completed.add(agent)
            remaining = [
                step for step in remaining if str(step.get("agent")) not in completed
            ]

        return [results_by_agent[str(step.get("agent"))] for step in steps]

    def synthesize(
        self,
        query: str,
        plan: JsonDict,
        agent_results: list[JsonDict],
        *,
        guardian_feedback: JsonDict | None = None,
    ) -> JsonDict:
        """Use Granite to merge specialist outputs into one briefing."""
        compact_results = [_compact_result(result) for result in agent_results]
        past_briefings = self.episodic_memory.query_briefings(query, limit=3)
        past_context = _format_past_briefings(past_briefings)
        guardian_feedback_block = ""
        if guardian_feedback:
            guardian_feedback_block = f"""
Previous Guardian validation flagged issues:
{json.dumps(guardian_feedback, indent=2)}

Revise the briefing to remove unsupported claims, label speculation clearly, and
keep claims tied to specialist sources. Do not invent new evidence.
"""
        prompt = f"""You are the Atlas Synthesis Agent.
Create a unified intelligence briefing from specialist agent outputs.

Original user query:
{query}

Execution plan:
{json.dumps(plan, indent=2)}

Specialist results:
{json.dumps(compact_results, indent=2)}

Relevant past briefings from episodic memory:
{past_context}
{guardian_feedback_block}

Instructions:
- Merge the market, geopolitical, and supply-chain perspectives.
- Include research/filing evidence when available.
- Explicitly call out confidence differences and live-data limitations.
- Resolve conflicts; if no direct conflict exists, say the outputs are complementary.
- Keep the briefing grounded in the specialist artifacts.
- If past briefings exist, briefly mention whether the current assessment changed.

Structure the briefing with markdown sections covering the main risk dimensions.
Include a short **Key sources** line at the end.

{MARKDOWN_FORMAT_INSTRUCTIONS}
"""
        combined_analysis = chat(prompt).strip()
        briefing = {
            "combined_analysis": combined_analysis,
            "per_agent_sources": _collect_sources(agent_results),
            "overall_confidence": _overall_confidence(agent_results),
            "execution_plan": plan,
            "agent_results": compact_results,
        }
        try:
            self.episodic_memory.log_briefing(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "query": query,
                    "execution_plan": plan,
                    "agent_results": compact_results,
                    "final_briefing": combined_analysis,
                    "confidence": briefing["overall_confidence"],
                    "sources": briefing["per_agent_sources"],
                }
            )
            print("[synthesis.memory] Logged briefing to episodic memory")
        except Exception as exc:
            print(f"[synthesis.memory] Episodic briefing logging skipped: {exc}")
        return briefing

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


def _format_past_briefings(records: list[Any]) -> str:
    if not records:
        return "(no similar past briefings found)"
    lines: list[str] = []
    for record in records:
        lines.append(
            f"- {record.timestamp.isoformat()} confidence={record.confidence} "
            f"query={record.query!r}\n  summary={record.final_briefing[:500]}"
        )
    return "\n".join(lines)
