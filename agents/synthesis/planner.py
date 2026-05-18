"""Execution-plan generation for the Synthesis Agent."""

from __future__ import annotations

import json
import re
from typing import Any

from services.llm import chat

JsonDict = dict[str, Any]


def create_execution_plan(query: str, agent_cards: list[JsonDict]) -> JsonDict:
    """Ask Granite to choose specialist agents and tasks.

    The plan is a small DAG object. Phase 4 runs it sequentially because the local
    machine has one Ollama/Granite pipeline, but `depends_on` makes the future
    parallel/conditional structure explicit.
    """
    cards_prompt = json.dumps(_summarize_cards(agent_cards), indent=2)
    prompt = f"""You are the Atlas Synthesis Planner.
Given a user query and available A2A Agent Cards, produce an execution plan.

User query:
{query}

Available agents:
{cards_prompt}

Rules:
- Output ONLY valid JSON, no markdown.
- Use the Agent Card `key` field as the step `agent` value.
- Include all agents needed for a cross-domain briefing.
- For Taiwan Strait / semiconductor / market-impact questions, include market,
  geopolitical, supply_chain, and research agents.
- Include the research agent for queries involving filings, earnings, SEC data,
  risk factors, annual reports, 10-K/10-Q, or company-specific financial details.
- For the market step in Taiwan Strait semiconductor scenarios, ask for valid
  Yahoo symbols such as TSM, NVDA, ASML, SMH, SOXX, and SPY; avoid delisted or
  ambiguous tickers.
- Sequential for now: every step may use depends_on: [] unless a dependency is obvious.

JSON schema:
{{
  "steps": [
    {{"agent": "market", "task": "task for that agent", "depends_on": []}}
  ],
  "rationale": "why these agents were selected"
}}
"""
    raw = chat(prompt)
    try:
        plan = _parse_json(raw)
    except json.JSONDecodeError:
        plan = _fallback_plan(query, agent_cards)

    steps = plan.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return _fallback_plan(query, agent_cards)
    return plan


def _summarize_cards(agent_cards: list[JsonDict]) -> list[JsonDict]:
    summaries: list[JsonDict] = []
    for card in agent_cards:
        summaries.append(
            {
                "key": agent_key(card),
                "name": card.get("name"),
                "url": card.get("url"),
                "description": card.get("description"),
                "skills": card.get("skills", []),
            }
        )
    return summaries


def agent_key(card: JsonDict) -> str:
    name = str(card.get("name", "")).lower()
    if "market" in name:
        return "market"
    if "geopolitical" in name:
        return "geopolitical"
    if "supply" in name:
        return "supply_chain"
    if "research" in name or "filing" in name:
        return "research"
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_") or "agent"


def _fallback_plan(query: str, agent_cards: list[JsonDict]) -> JsonDict:
    available = {agent_key(card) for card in agent_cards}
    preferred = ["geopolitical", "supply_chain", "research", "market"]
    steps = [
        {
            "agent": key,
            "task": _fallback_task(key, query),
            "depends_on": [],
        }
        for key in preferred
        if key in available
    ]
    if not steps:
        steps = [
            {
                "agent": agent_key(card),
                "task": query,
                "depends_on": [],
            }
            for card in agent_cards
        ]
    return {
        "steps": steps,
        "rationale": "Fallback plan based on available Agent Cards.",
    }


def _fallback_task(agent: str, query: str) -> str:
    if agent == "geopolitical":
        return f"Assess geopolitical escalation risks relevant to: {query}"
    if agent == "supply_chain":
        return f"Assess semiconductor supply-chain exposure relevant to: {query}"
    if agent == "market":
        return f"Assess market impact and relevant semiconductor equities for: {query}"
    if agent == "research":
        return f"Review SEC filing evidence and risk-factor disclosures relevant to: {query}"
    return query


def _parse_json(text: str) -> JsonDict:
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
