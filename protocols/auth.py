"""Shared security configuration for Atlas protocol clients and servers."""

from __future__ import annotations

import hmac
import os

from dotenv import load_dotenv

load_dotenv()


def mcp_auth_token() -> str | None:
    """Return the MCP bearer token when configured."""
    value = os.getenv("ATLAS_MCP_AUTH_TOKEN", "").strip()
    return value or None


def a2a_auth_token() -> str | None:
    """Return the A2A bearer token when configured."""
    value = os.getenv("ATLAS_A2A_AUTH_TOKEN", "").strip()
    return value or None


def api_auth_token() -> str | None:
    """Return the web API bearer token when configured.

    Falls back to ``ATLAS_MCP_AUTH_TOKEN`` so one local secret can gate MCP and API.
    """
    value = os.getenv("ATLAS_API_AUTH_TOKEN", "").strip()
    if value:
        return value
    return mcp_auth_token()


def auth_headers(token: str | None) -> dict[str, str]:
    """Build Authorization headers for protocol requests."""
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def tls_verify_enabled() -> bool:
    """Return whether TLS certificate verification is enabled."""
    return os.getenv("ATLAS_TLS_INSECURE", "").strip().lower() not in {"1", "true", "yes"}


def bearer_authorized(header_value: str | None, expected_token: str | None) -> bool:
    """Constant-time bearer token comparison for server-side checks."""
    if not expected_token:
        return True
    if not header_value or not header_value.startswith("Bearer "):
        return False
    provided = header_value.removeprefix("Bearer ").strip()
    return hmac.compare_digest(provided, expected_token)
