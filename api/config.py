"""Central port and security configuration for Atlas listening surfaces.

Every service that binds a port should be listed here so the full attack
surface is auditable in one place. Secrets are read from the environment —
never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

from protocols.auth import api_auth_token

load_dotenv()

Role = Literal["api", "frontend_dev", "ollama", "mcp", "a2a"]

BIND_HOST: str = os.getenv("ATLAS_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"

# --- API (FastAPI + production static bundle) ---
API_PORT: int = int(os.getenv("ATLAS_API_PORT", "8787"))
DEV_VITE_PORT: int = int(os.getenv("ATLAS_VITE_PORT", "5173"))
DEV_FRONTEND_ORIGIN: str = os.getenv(
    "ATLAS_DEV_FRONTEND_ORIGIN",
    f"http://127.0.0.1:{DEV_VITE_PORT}",
).strip()

# Query endpoint limits (mirror Rust governor posture for the inference path).
API_RATE_LIMIT_RPS: int = int(os.getenv("ATLAS_API_RATE_LIMIT_RPS", "10"))
MAX_CONCURRENT_INFERENCES: int = max(
    1,
    min(2, int(os.getenv("ATLAS_API_MAX_CONCURRENT_INFERENCES", "2"))),
)
MAX_QUERY_LENGTH: int = int(os.getenv("ATLAS_API_MAX_QUERY_LENGTH", "2000"))

# --- Ollama ---
OLLAMA_PORT: int = int(os.getenv("OLLAMA_PORT", "11434"))

# --- Rust MCP servers ---
MCP_MARKET_PORT: int = int(os.getenv("ATLAS_MCP_MARKET_PORT", "8001"))
MCP_EDGAR_PORT: int = int(os.getenv("ATLAS_MCP_EDGAR_PORT", "8002"))
MCP_TRADE_PORT: int = int(os.getenv("ATLAS_MCP_TRADE_PORT", "8003"))

# --- A2A specialist agents ---
A2A_MARKET_PORT: int = 9001
A2A_GEOPOLITICAL_PORT: int = 9002
A2A_SUPPLY_CHAIN_PORT: int = 9003
A2A_RESEARCH_PORT: int = 9004


@dataclass(frozen=True)
class ServiceEndpoint:
    """One auditable listen target."""

    name: str
    host: str
    port: int
    auth_env_var: str | None
    role: Role

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def auth_required(self) -> bool:
        """True when a bearer token env var is set for this service class."""
        if self.auth_env_var is None:
            return False
        return bool(os.getenv(self.auth_env_var, "").strip())


def _endpoint(
    name: str,
    port: int,
    role: Role,
    auth_env_var: str | None = None,
) -> ServiceEndpoint:
    return ServiceEndpoint(
        name=name,
        host=BIND_HOST,
        port=port,
        auth_env_var=auth_env_var,
        role=role,
    )


# Full listening surface — import this for audits and status responses.
SERVICE_ENDPOINTS: tuple[ServiceEndpoint, ...] = (
    _endpoint("atlas-api", API_PORT, "api", "ATLAS_API_AUTH_TOKEN"),
    _endpoint("vite-dev", DEV_VITE_PORT, "frontend_dev"),
    _endpoint("ollama", OLLAMA_PORT, "ollama"),
    _endpoint("mcp-market-data", MCP_MARKET_PORT, "mcp", "ATLAS_MCP_AUTH_TOKEN"),
    _endpoint("mcp-edgar", MCP_EDGAR_PORT, "mcp", "ATLAS_MCP_AUTH_TOKEN"),
    _endpoint("mcp-trade", MCP_TRADE_PORT, "mcp", "ATLAS_MCP_AUTH_TOKEN"),
    _endpoint("a2a-market", A2A_MARKET_PORT, "a2a", "ATLAS_A2A_AUTH_TOKEN"),
    _endpoint("a2a-geopolitical", A2A_GEOPOLITICAL_PORT, "a2a", "ATLAS_A2A_AUTH_TOKEN"),
    _endpoint("a2a-supply-chain", A2A_SUPPLY_CHAIN_PORT, "a2a", "ATLAS_A2A_AUTH_TOKEN"),
    _endpoint("a2a-research", A2A_RESEARCH_PORT, "a2a", "ATLAS_A2A_AUTH_TOKEN"),
)


def api_token_configured() -> bool:
    return api_auth_token() is not None


def mcp_urls() -> tuple[str, str, str]:
    market = f"http://{BIND_HOST}:{MCP_MARKET_PORT}"
    edgar = f"http://{BIND_HOST}:{MCP_EDGAR_PORT}"
    trade = f"http://{BIND_HOST}:{MCP_TRADE_PORT}"
    return market, edgar, trade


def a2a_agent_urls() -> tuple[str, str, str, str]:
    return (
        f"http://{BIND_HOST}:{A2A_MARKET_PORT}",
        f"http://{BIND_HOST}:{A2A_GEOPOLITICAL_PORT}",
        f"http://{BIND_HOST}:{A2A_SUPPLY_CHAIN_PORT}",
        f"http://{BIND_HOST}:{A2A_RESEARCH_PORT}",
    )
