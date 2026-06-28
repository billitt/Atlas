"""Status and session routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.config import api_token_configured, SERVICE_ENDPOINTS
from api.runtime import collect_status_payload
from api.security import AuthDep
from protocols.auth import api_auth_token

router = APIRouter()


@router.get("/status")
async def get_status(_auth: AuthDep) -> dict:
    """Token-gated system health (Ollama, MCP, memory, agents)."""
    payload = collect_status_payload()
    payload["api_auth_required"] = api_token_configured()
    payload["endpoints"] = [
        {
            "name": ep.name,
            "host": ep.host,
            "port": ep.port,
            "auth_required": ep.auth_required,
            "role": ep.role,
        }
        for ep in SERVICE_ENDPOINTS
    ]
    return payload


@router.get("/session")
async def get_session() -> dict:
    """Return bearer token for same-origin SPA clients when auth is configured.

    Unauthenticated — the token only works combined with localhost bind. When no
    token is configured, returns ``token: null`` (open demo mode).
    """
    token = api_auth_token()
    return {"token": token, "auth_required": token is not None}
