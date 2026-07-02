"""Boundary tests for BaseAgent reflection loop and JSON parsing."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agents.base import AgentResult, BaseAgent, Confidence, parse_json_from_llm
from agents.market.agent import MarketIntelligenceAgent


class StubAgent(BaseAgent):
    """Minimal agent for retry-loop tests without MCP or Granite."""

    def __init__(
        self,
        *,
        reflect_results: list[tuple[bool, str, Confidence]] | None = None,
        max_retries: int = 2,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.reflect_results = reflect_results or [(False, "fail", "LOW")]
        self.plan_calls = 0
        self.execute_calls = 0
        self.reflect_calls = 0

    async def plan(self, query: str) -> dict[str, Any]:
        self.plan_calls += 1
        return {"tool_calls": []}

    async def execute(self, query: str, plan: Any) -> AgentResult:
        self.execute_calls += 1
        return {
            "analysis": f"draft for {query}",
            "sources": [{"symbol": "AAPL", "regular_market_price": 180.0}],
            "confidence": "HIGH",
        }

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        self.reflect_calls += 1
        index = min(self.reflect_calls - 1, len(self.reflect_results) - 1)
        return self.reflect_results[index]


def test_json_parsing_handles_markdown_fences() -> None:
    parsed = parse_json_from_llm('```json\n{"passed": true, "confidence": "HIGH"}\n```')
    assert parsed["passed"] is True
    assert parsed["confidence"] == "HIGH"


def test_json_parsing_handles_embedded_braces() -> None:
    raw = 'Analysis preamble {"passed": false, "confidence": "LOW", "feedback": "bad"} trailing'
    parsed = parse_json_from_llm(raw)
    assert parsed["passed"] is False
    assert parsed["confidence"] == "LOW"


@pytest.mark.asyncio
async def test_reflection_rejects_ungrounded_claim() -> None:
    agent = MarketIntelligenceAgent(MagicMock())
    draft: AgentResult = {
        "analysis": "TSMC revenue grew 15% year over year.",
        "sources": [{"symbol": "TSM", "regular_market_price": 145.0}],
        "confidence": "HIGH",
    }
    verdict = {
        "passed": False,
        "confidence": "LOW",
        "feedback": "Revenue growth claim is not present in source quote data.",
    }
    with patch("agents.market.agent.chat", return_value=json.dumps(verdict)):
        passed, feedback, confidence = await agent.reflect("TSMC outlook", draft)

    assert passed is False
    assert confidence == "LOW"
    assert "Revenue" in feedback


@pytest.mark.asyncio
async def test_max_retries_respected() -> None:
    agent = StubAgent(max_retries=2)
    result = await agent.run("semiconductor risk")

    assert agent.plan_calls == 3
    assert agent.execute_calls == 3
    assert agent.reflect_calls == 3
    assert result["confidence"] == "LOW"
