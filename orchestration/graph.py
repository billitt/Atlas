"""LangGraph workflow for the Synthesis Agent."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.synthesis.agent import SynthesisAgent
from orchestration.state import SynthesisState

JsonDict = dict[str, Any]


def build_synthesis_graph(agent: SynthesisAgent):
    """Compile the Synthesis Agent into a traceable LangGraph workflow.

    We use a graph instead of plain function calls because Phase 4 is the first
    step toward observable multi-agent plans: each node can become an
    OpenTelemetry span, a checkpoint, or a human-review boundary later.
    """

    async def plan_node(state: SynthesisState) -> JsonDict:
        """START -> plan: ask Granite which A2A agents should be called."""
        query = state["query"]
        print("[graph.plan] Building execution plan")
        plan = agent.plan(query)
        return {"plan": plan}

    async def delegate_to_agents_node(state: SynthesisState) -> JsonDict:
        """plan -> delegate_to_agents: execute plan steps through A2A."""
        print("[graph.delegate_to_agents] Delegating plan steps over A2A")
        agent_results = await agent.delegate(state["plan"])
        sources = []
        for result in agent_results:
            metadata = result.get("artifact", {}).get("metadata", {})
            for source in metadata.get("sources", []):
                if isinstance(source, dict):
                    sources.append({"agent": result.get("agent"), **source})
        return {"agent_results": agent_results, "sources": sources}

    async def synthesize_node(state: SynthesisState) -> JsonDict:
        """delegate_to_agents -> synthesize: merge specialist outputs."""
        print("[graph.synthesize] Creating unified briefing")
        briefing = agent.synthesize(state["query"], state["plan"], state["agent_results"])
        return {
            "combined_analysis": briefing["combined_analysis"],
            "confidence": briefing["overall_confidence"],
            "briefing": briefing,
        }

    graph = StateGraph(SynthesisState)

    # Nodes are named for the durable phases we want to trace in future observability.
    graph.add_node("plan", plan_node)
    graph.add_node("delegate_to_agents", delegate_to_agents_node)
    graph.add_node("synthesize", synthesize_node)

    # Edges define the workflow DAG explicitly:
    # START -> plan -> delegate_to_agents -> synthesize -> END.
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "delegate_to_agents")
    graph.add_edge("delegate_to_agents", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
