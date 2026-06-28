"""Agent status route."""

from __future__ import annotations

from fastapi import APIRouter

from api.runtime import _fetch_agent_cards_status
from api.security import AuthDep

router = APIRouter()


@router.get("/agents")
async def get_agents(_auth: AuthDep) -> dict:
    """Specialist agent cards and reachability probes."""
    return {"agents": _fetch_agent_cards_status()}
