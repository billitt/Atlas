"""Base agent pattern: plan → execute → reflect, with optional retries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, Literal, TypedDict

from observability.tracing import get_tracer

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
_tracer = get_tracer("agents.base")


class AgentResult(TypedDict):
    """Structured output returned to callers after a successful run."""

    analysis: str
    sources: list[dict[str, Any]]
    confidence: Confidence


class BaseAgent(ABC):
    """Shared agent loop used by all Atlas specialist agents."""

    def __init__(self, *, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    @property
    def agent_name(self) -> str:
        """Short agent label used in traces and episodic memory."""
        mapping = {
            "MarketIntelligenceAgent": "market",
            "GeopoliticalRiskAgent": "geopolitical",
            "SupplyChainAgent": "supply_chain",
            "ResearchFilingAgent": "research",
        }
        return mapping.get(self.__class__.__name__, self.__class__.__name__.replace("Agent", "").lower())

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

        with _tracer.start_as_current_span("agent.run") as run_span:
            run_span.set_attribute("agent_name", self.agent_name)
            run_span.set_attribute("query", query[:500])
            run_start = perf_counter()

            while attempt <= self.max_retries:
                print(f"\n=== Agent attempt {attempt + 1}/{self.max_retries + 1} ===")

                with _tracer.start_as_current_span("agent.plan") as plan_span:
                    plan_span.set_attribute("agent_name", self.agent_name)
                    plan_span.set_attribute("attempt_number", attempt + 1)
                    print("[plan] Deciding which data sources to query...")
                    plan = await self.plan(query)
                    if reflection_feedback:
                        print(f"[plan] Incorporating reflection feedback: {reflection_feedback[:200]}...")

                with _tracer.start_as_current_span("agent.execute") as execute_span:
                    execute_span.set_attribute("agent_name", self.agent_name)
                    execute_span.set_attribute("attempt_number", attempt + 1)
                    exec_start = perf_counter()
                    print("[execute] Fetching MCP data and drafting analysis...")
                    draft = await self.execute(query, plan)
                    execute_span.set_attribute("duration_ms", round((perf_counter() - exec_start) * 1000, 3))
                    last_draft = draft

                with _tracer.start_as_current_span("agent.reflect") as reflect_span:
                    reflect_span.set_attribute("agent_name", self.agent_name)
                    reflect_span.set_attribute("attempt_number", attempt + 1)
                    reflect_start = perf_counter()
                    print("[reflect] Checking grounding and confidence...")
                    passed, feedback, confidence = await self.reflect(query, draft)
                    draft["confidence"] = confidence
                    reflect_span.set_attribute("reflection_passed", passed)
                    reflect_span.set_attribute("confidence", confidence)
                    reflect_span.set_attribute("duration_ms", round((perf_counter() - reflect_start) * 1000, 3))

                if passed:
                    print(f"[reflect] PASSED - confidence {confidence}")
                    run_span.set_attribute("confidence", confidence)
                    run_span.set_attribute("duration_ms", round((perf_counter() - run_start) * 1000, 3))
                    return draft

                reflection_feedback = feedback
                print(f"[reflect] FAILED - {feedback}")
                attempt += 1

            print("[agent] Max retries reached; returning last draft with reduced confidence.")
            if last_draft is not None:
                if last_draft["confidence"] == "HIGH":
                    last_draft["confidence"] = "LOW"
                run_span.set_attribute("confidence", last_draft["confidence"])
                run_span.set_attribute("duration_ms", round((perf_counter() - run_start) * 1000, 3))
                return last_draft

        raise RuntimeError("agent produced no draft")
