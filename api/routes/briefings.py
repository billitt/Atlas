"""Briefing history route."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.security import AuthDep
from memory.episodic import EpisodicMemory

router = APIRouter()


@router.get("/briefings")
async def list_briefings(
    _auth: AuthDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Recent briefing records from episodic memory."""
    episodic = EpisodicMemory()
    records = episodic.query_briefings("", limit=limit)
    return {
        "briefings": [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(timespec="seconds"),
                "query": record.query,
                "briefing_type": record.briefing_type,
                "confidence": record.confidence,
                "trace_id": record.trace_id,
                "duration_seconds": record.duration_seconds,
                "summary": record.final_briefing[:500],
                "delta_from_last": record.delta_from_last,
            }
            for record in records
        ]
    }
