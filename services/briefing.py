"""Scheduled briefing generation over the full Atlas synthesis pipeline."""

from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from memory.episodic import EpisodicMemory
from observability.run_logger import save_run
from observability.tracing import get_current_trace_id, get_tracer
from orchestration.graph import build_synthesis_graph, run_synthesis_graph

JsonDict = dict[str, Any]
_tracer = get_tracer("services.briefing")

DEFAULT_WATCHLIST = [
    "semiconductor supply chain",
    "US-China trade tensions",
    "major market movements",
    "SEC filing activity",
]


class BriefingEngine:
    """Generate daily, weekly, or custom briefings from Atlas agents."""

    def __init__(
        self,
        synthesis_agent: SynthesisAgent,
        *,
        episodic_memory: EpisodicMemory | None = None,
        guardian: GuardianAgent | None = None,
        briefing_type: str = "daily",
    ) -> None:
        self.synthesis_agent = synthesis_agent
        self.episodic_memory = episodic_memory or EpisodicMemory()
        self.guardian = guardian or GuardianAgent()
        self.briefing_type = briefing_type

    async def generate_briefing(self, topics: list[str] | None = None) -> JsonDict:
        """Run one synthesis+Guardian pipeline per topic and compile a briefing."""
        selected_topics = topics or DEFAULT_WATCHLIST
        started_at = datetime.now().isoformat(timespec="seconds")
        start_time = perf_counter()
        graph = build_synthesis_graph(self.synthesis_agent, guardian=self.guardian)
        sections: list[JsonDict] = []
        deltas: list[str] = []

        with _tracer.start_as_current_span("briefing.generate") as parent_span:
            parent_span.set_attribute("briefing_type", self.briefing_type)
            parent_span.set_attribute("topics_count", len(selected_topics))
            trace_id = get_current_trace_id()
            if trace_id:
                parent_span.set_attribute("trace_id", trace_id)

            for topic in selected_topics:
                with _tracer.start_as_current_span("briefing.topic") as topic_span:
                    topic_span.set_attribute("topic", topic)
                    last = self.episodic_memory.get_last_briefing(topic)
                    query = _topic_query(topic)
                    print(f"[briefing] Generating section: {topic}")
                    state = await run_synthesis_graph(
                        graph,
                        {
                            "query": query,
                            "messages": [("user", query)],
                            "agent_cards": self.synthesis_agent.agent_cards,
                            "agent_results": [],
                            "sources": [],
                            "guardian_retries": 0,
                        },
                    )
                    briefing = state["briefing"]
                    delta = _delta_from_last(topic, briefing, last)
                    deltas.append(delta)
                    topic_span.set_attribute("confidence", briefing.get("overall_confidence", "LOW"))
                    sections.append(
                        {
                            "topic": topic,
                            "analysis": briefing["combined_analysis"],
                            "sources": briefing["per_agent_sources"],
                            "confidence": briefing["overall_confidence"],
                            "guardian_verdict": briefing.get("guardian_verdict", {}),
                            "delta_from_last": delta,
                            "execution_plan": briefing["execution_plan"],
                            "agent_results": briefing["agent_results"],
                        }
                    )

            duration_seconds = round(perf_counter() - start_time, 3)
            parent_span.set_attribute("duration_ms", duration_seconds * 1000)
            compiled = {
                "timestamp": started_at,
                "briefing_type": self.briefing_type,
                "topics": selected_topics,
                "sections": sections,
                "delta_from_last": "\n".join(deltas),
                "overall_risk_level": _overall_risk_level(sections),
                "duration_seconds": duration_seconds,
                "trace_id": trace_id,
            }
            self._persist(compiled)
            return compiled

    def _persist(self, briefing: JsonDict) -> None:
        run_data = {
            "timestamp": briefing["timestamp"],
            "query": "; ".join(briefing["topics"]),
            "briefing_type": briefing["briefing_type"],
            "topics": briefing["topics"],
            "sections_count": len(briefing["sections"]),
            "overall_risk_level": briefing["overall_risk_level"],
            "duration_seconds": briefing["duration_seconds"],
            "agent_results": briefing["sections"],
            "sources": [source for section in briefing["sections"] for source in section["sources"]],
            "confidence": briefing["overall_risk_level"],
            "final_briefing": _briefing_text_for_memory(briefing),
            "guardian_verdict": {"sections": [section["guardian_verdict"] for section in briefing["sections"]]},
            "delta_from_last": briefing["delta_from_last"],
            "trace_id": briefing.get("trace_id") or get_current_trace_id(),
            "per_topic": [
                {
                    "topic": section["topic"],
                    "confidence": section["confidence"],
                    "sources_count": len(section["sources"]),
                    "delta_detected": not section["delta_from_last"].startswith("No prior"),
                }
                for section in briefing["sections"]
            ],
        }
        save_run(run_data)
        self.episodic_memory.log_briefing(run_data)


def _topic_query(topic: str) -> str:
    return (
        "Generate an intelligence briefing section for this watchlist topic: "
        f"{topic}. Include relevant market, geopolitical, supply-chain, and filing context "
        "when available."
    )


def _delta_from_last(topic: str, briefing: JsonDict, last: Any | None) -> str:
    confidence = briefing.get("overall_confidence", "LOW")
    if last is None:
        return f"No prior briefing found for {topic}; baseline created at {briefing.get('timestamp', 'now')}."
    previous = getattr(last, "confidence", "LOW")
    if previous != confidence:
        return f"{topic}: confidence changed from {previous} to {confidence}."
    return f"{topic}: confidence remains {confidence}; compare current analysis with prior record {last.id}."


def _overall_risk_level(sections: list[JsonDict]) -> str:
    ranks = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    risk = "LOW"
    for section in sections:
        guardian = section.get("guardian_verdict", {}) or {}
        flags = guardian.get("flags") or []
        confidence = str(section.get("confidence", "LOW")).upper()
        if confidence not in ranks:
            confidence = "LOW"
        section_risk = "HIGH" if flags or confidence == "LOW" else confidence
        if ranks[section_risk] > ranks[risk]:
            risk = section_risk
    return risk


def _briefing_text_for_memory(briefing: JsonDict) -> str:
    lines = [
        f"{briefing['briefing_type']} briefing risk={briefing['overall_risk_level']}",
        briefing["delta_from_last"],
    ]
    for section in briefing["sections"]:
        lines.append(f"\n[{section['topic']}]\n{section['analysis']}")
    return "\n".join(lines)
