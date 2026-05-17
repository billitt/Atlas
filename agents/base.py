"""Base agent pattern: plan → execute → reflect, with optional retries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


class AgentResult(TypedDict):
    """Structured output returned to callers after a successful run."""

    analysis: str
    sources: list[dict[str, Any]]
    confidence: Confidence


class BaseAgent(ABC):
    """Shared agent loop used by all Atlas specialist agents.

    Why three LLM phases?
      1. plan    — decide *what data* to fetch (tool selection), without hallucinating prices.
      2. execute — analyze *real* MCP tool output (grounded in fetched JSON).
      3. reflect — critique the draft; catch unsupported claims before the user sees them.

    If reflection fails, we retry the full loop (up to max_retries times) so the agent
    can replan or rewrite with explicit feedback. OpenTelemetry hooks will replace prints later.
    """

    def __init__(self, *, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    @abstractmethod
    async def plan(self, query: str) -> Any:
        """Decide which tools/data sources to use for this query."""

    @abstractmethod
    async def execute(self, query: str, plan: Any) -> AgentResult:
        """Fetch data via MCP (and other I/O), then produce a draft analysis."""

    @abstractmethod
    async def reflect(self, query: str, draft: AgentResult) -> tuple[bool, str, Confidence]:
        """Review draft quality. Returns (passed, feedback, confidence)."""

    async def run(self, query: str) -> AgentResult:
        """Run plan → execute → reflect; retry when reflection does not pass."""
        attempt = 0
        last_draft: AgentResult | None = None
        reflection_feedback = ""

        while attempt <= self.max_retries:
            print(f"\n=== Agent attempt {attempt + 1}/{self.max_retries + 1} ===")

            print("[plan] Deciding which data sources to query...")
            plan = await self.plan(query)
            if reflection_feedback:
                print(f"[plan] Incorporating reflection feedback: {reflection_feedback[:200]}...")

            print("[execute] Fetching MCP data and drafting analysis...")
            draft = await self.execute(query, plan)
            last_draft = draft

            print("[reflect] Checking grounding and confidence...")
            passed, feedback, confidence = await self.reflect(query, draft)
            draft["confidence"] = confidence

            if passed:
                print(f"[reflect] PASSED - confidence {confidence}")
                return draft

            reflection_feedback = feedback
            print(f"[reflect] FAILED - {feedback}")
            attempt += 1

        print("[agent] Max retries reached; returning last draft with reduced confidence.")
        if last_draft is not None:
            if last_draft["confidence"] == "HIGH":
                last_draft["confidence"] = "LOW"
            return last_draft

        raise RuntimeError("agent produced no draft")
