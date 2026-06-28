"""Shared MCP server URLs and health-check targets for Atlas Python services."""

from __future__ import annotations

import os

MCP_BIND_HOST: str = os.getenv("ATLAS_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
MCP_MARKET_PORT: int = int(os.getenv("ATLAS_MCP_MARKET_PORT", "8001"))
MCP_EDGAR_PORT: int = int(os.getenv("ATLAS_MCP_EDGAR_PORT", "8002"))
MCP_TRADE_PORT: int = int(os.getenv("ATLAS_MCP_TRADE_PORT", "8003"))


def mcp_market_url() -> str:
    return f"http://{MCP_BIND_HOST}:{MCP_MARKET_PORT}"


def mcp_edgar_url() -> str:
    return f"http://{MCP_BIND_HOST}:{MCP_EDGAR_PORT}"


def mcp_trade_url() -> str:
    return f"http://{MCP_BIND_HOST}:{MCP_TRADE_PORT}"


MCP_HEALTH_TARGETS: tuple[tuple[str, str], ...] = (
    ("mcp-market-data", mcp_market_url()),
    ("mcp-edgar", mcp_edgar_url()),
    ("mcp-trade", mcp_trade_url()),
)
