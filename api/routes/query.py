"""Query streaming route — SSE from LangGraph astream (updates + custom)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
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


# --- Source normalization -------------------------------------------------
#
# Specialist agents emit `sources` in different shapes:
#   - Market (mcp):        {"type": "mcp", "symbol": "TSM", "provider": ...}
#   - Geopolitical/Supply  {"type": "semantic_memory", "source": "seed_gdelt",
#     (seed match):         "region": "Taiwan Strait", "date": ...}
#   - Geopolitical/Supply  {"type": "model_knowledge"|"semantic_memory",
#     (summary note):       "note": ..., "planned_dimensions": [...]}
#   - Research (EDGAR):    {"tool": "company_filings", "arguments": {...}, "result": {...}}
#
# We collapse all of them to one canonical item the UI can render uniformly:
#   {"label": str, "detail"?: str, "url"?: str}
# Items with no derivable label are omitted (never rendered as "Source").

_SEED_SOURCE_LABELS = {
    "seed_gdelt": "GDELT event",
    "seed_comtrade": "UN Comtrade trade flow",
    "seed_sec_filing": "SEC filing excerpt",
    "sec_edgar": "SEC EDGAR filing",
}

_EDGAR_TOOL_LABELS = {
    "company_filings": "Company filings",
    "filing_text": "Filing text",
    "full_text_search": "Full-text search",
}


def _clean_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _domain(url: str) -> str:
    return urlparse(url).netloc or url


def _src(label: str, detail: str | None = None, url: str | None = None) -> JsonDict:
    item: JsonDict = {"label": label}
    if detail:
        item["detail"] = detail
    if url:
        item["url"] = url
    return item


def _normalize_source(source: Any) -> JsonDict | None:
    """Collapse any specialist source shape to {label, detail?, url?} or None."""
    if isinstance(source, str):
        text = source.strip()
        return _src(text[:80]) if text else None
    if not isinstance(source, dict):
        return None

    url = _clean_str(source.get("url"))

    # 1. explicit human-readable identifier (covers Market's `symbol`)
    for key in ("title", "name", "symbol"):
        val = _clean_str(source.get(key))
        if val:
            detail = _clean_str(source.get("provider")) or _clean_str(source.get("server"))
            return _src(val, detail, url)

    # 2. Research / EDGAR fetched shape: {tool, arguments, result}
    tool = _clean_str(source.get("tool"))
    if tool:
        args = source.get("arguments") if isinstance(source.get("arguments"), dict) else {}
        ident = (
            _clean_str(args.get("ticker"))
            or _clean_str(args.get("cik"))
            or _clean_str(args.get("query"))
        )
        base = _EDGAR_TOOL_LABELS.get(tool, tool.replace("_", " ").capitalize())
        label = f"SEC EDGAR — {base}" + (f" ({ident})" if ident else "")
        detail = _clean_str(args.get("accession_number"))
        return _src(label, detail, url)

    # 3. Seed / semantic-memory match shape: {source, region, ticker, date}
    seed = _clean_str(source.get("source"))
    if seed:
        base = _SEED_SOURCE_LABELS.get(seed, seed.replace("seed_", "").replace("_", " ").title())
        qualifier = _clean_str(source.get("region")) or _clean_str(source.get("ticker"))
        label = f"{base} — {qualifier}" if qualifier else base
        return _src(label, _clean_str(source.get("date")), url)

    # 4. Note-only summary sources (model knowledge / semantic memory)
    src_type = _clean_str(source.get("type"))
    note = _clean_str(source.get("note"))
    if src_type == "model_knowledge":
        return _src("Model knowledge (no live feed)")
    if src_type == "semantic_memory" or note:
        return _src("Semantic memory context", note)

    # 5. url domain, then id, then a text excerpt
    if url:
        return _src(_domain(url), None, url)
    sid = _clean_str(source.get("id"))
    if sid:
        return _src(sid)
    text = _clean_str(source.get("excerpt")) or _clean_str(source.get("text"))
    if text:
        return _src(text[:80] + ("…" if len(text) > 80 else ""))

    return None


def _normalize_sources(raw: Any) -> list[JsonDict]:
    if not isinstance(raw, list):
        return []
    out: list[JsonDict] = []
    seen: set[tuple[str, str | None]] = set()
    for item in raw:
        norm = _normalize_source(item)
        if norm is None:
            continue
        key = (norm["label"], norm.get("detail"))
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def _compact_specialist(result: JsonDict) -> JsonDict:
    metadata = result.get("artifact", {}).get("metadata", {})
    agent = str(result.get("agent", ""))
    return {
        "agent": agent,
        "label": SPECIALIST_LABELS.get(agent, agent),
        "analysis": metadata.get("analysis"),
        "confidence": metadata.get("confidence"),
        "sources": _normalize_sources(metadata.get("sources", [])),
        "task": result.get("task"),
    }


async def _stream_graph_events(
    app_graph: Any,
    initial_state: JsonDict,
    episodic_memory: EpisodicMemory,
    query: str,
    started_at: str,
    start_time: float,
):
    """Yield SSE chunks from LangGraph astream (stream_mode updates + custom).

    ``stream_mode=["updates", "custom"]`` yields ``(mode, chunk)`` tuples:
    - ``"custom"`` chunks carry per-agent specialist results emitted by
      ``delegate_to_agents_node`` as each specialist completes.
    - ``"updates"`` chunks are ``{node_name: state_delta}`` fired once per
      graph super-step, providing deterministic node-level progress.
    """
    accumulated: JsonDict = dict(initial_state)
    try:
        yield format_sse("started", {"query": query})

        async for mode, chunk in app_graph.astream(
            initial_state, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                # Per-agent events emitted by the delegate node's stream writer.
                if (
                    isinstance(chunk, dict)
                    and chunk.get("_atlas_type") == "specialist_result"
                ):
                    yield format_sse("specialist", _compact_specialist(chunk["result"]))
                continue

            # mode == "updates": chunk is {node_name: state_delta}
            for node, output in chunk.items():
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

                elif node == "delegate_to_agents":
                    # Specialist tiles were already sent as custom events above;
                    # this marks the delegation phase as fully complete.
                    agent_results = output.get("agent_results") or []
                    yield format_sse(
                        "delegate",
                        {"status": "complete", "count": len(agent_results)},
                    )

                elif node == "synthesize":
                    briefing = output.get("briefing") or {}
                    yield format_sse(
                        "synthesize",
                        {
                            "status": "complete",
                            "combined_analysis": output.get("combined_analysis"),
                            "confidence": output.get("confidence"),
                            "sources": _normalize_sources(briefing.get("per_agent_sources", [])),
                        },
                    )

                elif node == "guardian":
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

        # Emit a briefing copy whose per_agent_sources use the canonical shape.
        final_briefing = {
            **briefing,
            "per_agent_sources": _normalize_sources(briefing.get("per_agent_sources", [])),
        }
        yield format_sse(
            "final",
            {
                "briefing": final_briefing,
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
