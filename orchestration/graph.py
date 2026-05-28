"""LangGraph workflow for the Synthesis Agent."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from observability.tracing import get_current_trace_id, get_tracer
from orchestration.state import SynthesisState

JsonDict = dict[str, Any]
_tracer = get_tracer("orchestration.graph")


def build_synthesis_graph(
    agent: SynthesisAgent,
    *,
    guardian: GuardianAgent | None = None,
    max_guardian_retries: int = 1,
):
    """Compile the Synthesis Agent into a traceable LangGraph workflow."""

    async def plan_node(state: SynthesisState) -> JsonDict:
        """START -> plan: ask Granite which A2A agents should be called."""
        query = state["query"]
        with _tracer.start_as_current_span("graph.plan") as span:
            span.set_attribute("node_name", "plan")
            span.set_attribute("query", query)
            print("[graph.plan] Building execution plan")
            plan = agent.plan(query)
            steps = plan.get("steps", []) if isinstance(plan, dict) else []
            span.set_attribute("plan_step_count", len(steps))
            return {"plan": plan}

    async def delegate_to_agents_node(state: SynthesisState) -> JsonDict:
        """plan -> delegate_to_agents: execute plan steps through A2A."""
        with _tracer.start_as_current_span("graph.delegate_to_agents") as span:
            span.set_attribute("node_name", "delegate_to_agents")
            span.set_attribute("query", state["query"])
            plan = state.get("plan") or {}
            steps = plan.get("steps", []) if isinstance(plan, dict) else []
            span.set_attribute("plan_step_count", len(steps))
            print("[graph.delegate_to_agents] Delegating plan steps over A2A")
            agent_results = await agent.delegate(state["plan"])
            span.set_attribute("agent_count", len(agent_results))
            sources = []
            for result in agent_results:
                metadata = result.get("artifact", {}).get("metadata", {})
                for source in metadata.get("sources", []):
                    if isinstance(source, dict):
                        sources.append({"agent": result.get("agent"), **source})
            return {"agent_results": agent_results, "sources": sources}

    async def synthesize_node(state: SynthesisState) -> JsonDict:
        """delegate_to_agents -> synthesize: merge specialist outputs."""
        with _tracer.start_as_current_span("graph.synthesize") as span:
            span.set_attribute("node_name", "synthesize")
            span.set_attribute("query", state["query"])
            span.set_attribute("agent_count", len(state.get("agent_results") or []))
            print("[graph.synthesize] Creating unified briefing")
            guardian_feedback = (
                state.get("guardian_verdict") if state.get("guardian_retries", 0) else None
            )
            briefing = agent.synthesize(
                state["query"],
                state["plan"],
                state["agent_results"],
                guardian_feedback=guardian_feedback,
            )
            span.set_attribute("confidence", briefing.get("overall_confidence", "LOW"))
            return {
                "combined_analysis": briefing["combined_analysis"],
                "confidence": briefing["overall_confidence"],
                "briefing": briefing,
            }

    async def guardian_node(state: SynthesisState) -> JsonDict:
        """synthesize -> guardian: validate grounding before user-facing output."""
        with _tracer.start_as_current_span("graph.guardian") as span:
            span.set_attribute("node_name", "guardian")
            span.set_attribute("query", state["query"])
            print("[graph.guardian] Validating synthesized briefing")
            validator = guardian or GuardianAgent()
            verdict = validator.validate(
                state["query"],
                state["briefing"],
                state["agent_results"],
                state["sources"],
            )
            span.set_attribute("overall_confidence", verdict.get("overall_confidence", "LOW"))
            span.set_attribute("passed", bool(verdict.get("passed", False)))
            briefing = {**state["briefing"], "guardian_verdict": verdict}
            briefing["overall_confidence"] = verdict["overall_confidence"]
            retries = state.get("guardian_retries", 0)
            if verdict["overall_confidence"] == "LOW":
                retries += 1
            return {
                "guardian_verdict": verdict,
                "guardian_retries": retries,
                "confidence": verdict["overall_confidence"],
                "briefing": briefing,
            }

    def guardian_route(state: SynthesisState) -> str:
        verdict = state.get("guardian_verdict", {})
        confidence = str(verdict.get("overall_confidence", "LOW")).upper()
        retries = state.get("guardian_retries", 0)
        if confidence == "LOW" and retries <= max_guardian_retries:
            print("[graph.guardian] LOW confidence; retrying synthesis once")
            return "retry_synthesize"
        return "done"

    graph = StateGraph(SynthesisState)

    graph.add_node("plan", plan_node)
    graph.add_node("delegate_to_agents", delegate_to_agents_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("guardian", guardian_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "delegate_to_agents")
    graph.add_edge("delegate_to_agents", "synthesize")
    graph.add_edge("synthesize", "guardian")
    graph.add_conditional_edges(
        "guardian",
        guardian_route,
        {"retry_synthesize": "synthesize", "done": END},
    )

    return graph.compile()


async def run_synthesis_graph(app: Any, state: SynthesisState) -> SynthesisState:
    """Run the compiled synthesis graph under a parent trace span."""
    with _tracer.start_as_current_span("synthesis.graph") as span:
        span.set_attribute("query", state.get("query", ""))
        trace_id = get_current_trace_id()
        if trace_id:
            span.set_attribute("trace_id", trace_id)
        result = await app.ainvoke(state)
        plan = result.get("plan") or {}
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        span.set_attribute("plan_step_count", len(steps))
        span.set_attribute("agent_count", len(result.get("agent_results") or []))
        return result
