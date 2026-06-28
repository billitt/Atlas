"""Query streaming route — SSE from LangGraph astream_events."""

from __future__ import annotations

import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agents.guardian.agent import GuardianAgent
from api.config import MAX_QUERY_LENGTH
from api.runtime import build_synthesis_stack
from api.security import AuthDep, RateLimitDep, acquire_inference_slot, release_inference_slot
from api.sse import format_sse
from memory.episodic import EpisodicMemory
from observability.run_logger import save_run
from observability.tracing import get_current_trace_id
from orchestration.graph import build_synthesis_graph

JsonDict = dict[str, Any]

router = APIRouter()

# Business-facing specialist labels (no protocol jargon).
SPECIALIST_LABELS: dict[str, str] = {
    "market": "Market",
    "geopolitical": "Geopolitical",
    "supply_chain": "Supply Chain",
    "research": "Filings",
}


class QueryBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)


def _compact_specialist(result: JsonDict) -> JsonDict:
    metadata = result.get("artifact", {}).get("metadata", {})
    agent = str(result.get("agent", ""))
    return {
        "agent": agent,
        "label": SPECIALIST_LABELS.get(agent, agent),
        "analysis": metadata.get("analysis"),
        "confidence": metadata.get("confidence"),
        "sources": metadata.get("sources", []),
        "task": result.get("task"),
    }


def _node_from_event(event: JsonDict) -> str | None:
    metadata = event.get("metadata") or {}
    node = metadata.get("langgraph_node")
    if node:
        return str(node)
    name = event.get("name")
    if name in {"plan", "delegate_to_agents", "synthesize", "guardian"}:
        return str(name)
    return None


async def _stream_graph_events(
    app_graph: Any,
    initial_state: JsonDict,
    episodic_memory: EpisodicMemory,
    query: str,
    started_at: str,
    start_time: float,
):
    """Yield SSE chunks from LangGraph astream_events."""
    accumulated: JsonDict = dict(initial_state)
    try:
        yield format_sse("started", {"query": query})

        async for event in app_graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            if kind != "on_chain_end":
                continue

            node = _node_from_event(event)
            if not node:
                continue

            output = (event.get("data") or {}).get("output") or {}
            accumulated.update(output)

            if node == "plan":
                plan = output.get("plan") or {}
                yield format_sse(
                    "plan",
                    {
                        "status": "complete",
                        "step_count": len(plan.get("steps", [])),
                    },
                )
                continue

            if node == "delegate_to_agents":
                agent_results = output.get("agent_results") or []
                for result in agent_results:
                    yield format_sse("specialist", _compact_specialist(result))
                yield format_sse(
                    "delegate",
                    {"status": "complete", "count": len(agent_results)},
                )
                continue

            if node == "synthesize":
                briefing = output.get("briefing") or {}
                yield format_sse(
                    "synthesize",
                    {
                        "status": "complete",
                        "combined_analysis": output.get("combined_analysis"),
                        "confidence": output.get("confidence"),
                        "sources": briefing.get("per_agent_sources", []),
                    },
                )
                continue

            if node == "guardian":
                verdict = output.get("guardian_verdict") or {}
                yield format_sse(
                    "guardian",
                    {
                        "status": "complete",
                        "passed": verdict.get("passed"),
                        "overall_confidence": verdict.get("overall_confidence"),
                        "summary": verdict.get("summary"),
                        "flags": verdict.get("flags", []),
                        "claim_checks": verdict.get("claim_checks", []),
                    },
                )
                continue

        briefing = accumulated.get("briefing") or {}
        guardian_verdict = briefing.get("guardian_verdict") or accumulated.get(
            "guardian_verdict", {}
        )
        duration_seconds = round(perf_counter() - start_time, 3)
        trace_id = get_current_trace_id()

        run_data = {
            "timestamp": started_at,
            "query": query,
            "execution_plan": briefing.get("execution_plan"),
            "agent_results": briefing.get("agent_results"),
            "sources": briefing.get("per_agent_sources"),
            "confidence": briefing.get("overall_confidence"),
            "final_briefing": briefing.get("combined_analysis"),
            "guardian_verdict": guardian_verdict,
            "duration_seconds": duration_seconds,
            "trace_id": trace_id,
        }
        save_run(run_data)
        episodic_memory.log_briefing(run_data)

        yield format_sse(
            "final",
            {
                "briefing": briefing,
                "trace_id": trace_id,
                "duration_seconds": duration_seconds,
                "confidence": briefing.get("overall_confidence"),
                "guardian_verdict": guardian_verdict,
            },
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        yield format_sse("error", {"message": "Query failed."})
    finally:
        release_inference_slot()


@router.post("/query")
async def post_query(
    body: QueryBody,
    _auth: AuthDep,
    _rate: RateLimitDep,
    request: Request,
) -> Any:
    """Stream synthesis results as Server-Sent Events."""
    from fastapi.responses import StreamingResponse

    agent_cards = request.app.state.agent_cards
    if not agent_cards:
        raise HTTPException(status_code=503, detail="Specialists not ready.")

    await acquire_inference_slot()
    started_at = datetime.now().isoformat(timespec="seconds")
    start_time = perf_counter()

    synthesis_agent, episodic_memory = build_synthesis_stack(agent_cards)
    guardian = GuardianAgent()
    app_graph = build_synthesis_graph(synthesis_agent, guardian=guardian)

    initial_state: JsonDict = {
        "query": body.query.strip(),
        "messages": [("user", body.query.strip())],
        "agent_cards": agent_cards,
        "agent_results": [],
        "sources": [],
        "guardian_retries": 0,
    }

    return StreamingResponse(
        _stream_graph_events(
            app_graph,
            initial_state,
            episodic_memory,
            body.query.strip(),
            started_at,
            start_time,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
