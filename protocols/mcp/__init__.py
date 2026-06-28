"""MCP client utilities for Atlas Rust MCP servers."""

from protocols.mcp.client import McpClient
from protocols.mcp.endpoints import (
    MCP_HEALTH_TARGETS,
    MCP_BIND_HOST,
    MCP_EDGAR_PORT,
    MCP_MARKET_PORT,
    MCP_TRADE_PORT,
    mcp_edgar_url,
    mcp_market_url,
    mcp_trade_url,
)

__all__ = [
    "McpClient",
    "MCP_BIND_HOST",
    "MCP_EDGAR_PORT",
    "MCP_HEALTH_TARGETS",
    "MCP_MARKET_PORT",
    "MCP_TRADE_PORT",
    "mcp_edgar_url",
    "mcp_market_url",
    "mcp_trade_url",
]
