"""Boundary tests for MCP client and market tool JSON handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agents.market.tools import call_get_quote
from protocols.mcp.client import McpClient


def _mock_response(payload: Any, *, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_initialize_rejects_non_dict_result() -> None:
    client = McpClient("http://localhost:8001")
    with patch(
        "protocols.mcp.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=_mock_response({"jsonrpc": "2.0", "id": 1, "result": "string"}),
    ):
        with pytest.raises(RuntimeError, match="unexpected initialize result"):
            await client.initialize()


@pytest.mark.asyncio
async def test_list_tools_returns_empty_when_tools_key_missing() -> None:
    client = McpClient("http://localhost:8001")
    with patch(
        "protocols.mcp.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=_mock_response({"jsonrpc": "2.0", "id": 1, "result": {}}),
    ):
        tools = await client.list_tools()
        assert tools == []


@pytest.mark.asyncio
async def test_call_tool_rejects_non_dict_result() -> None:
    client = McpClient("http://localhost:8001")
    with patch(
        "protocols.mcp.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=_mock_response({"jsonrpc": "2.0", "id": 1, "result": []}),
    ):
        with pytest.raises(RuntimeError, match="unexpected tools/call result"):
            await client.call_tool("get_quote", {"symbol": "AAPL"})


@pytest.mark.asyncio
async def test_request_surfaces_jsonrpc_error() -> None:
    client = McpClient("http://localhost:8001")
    with patch(
        "protocols.mcp.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=_mock_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "bad params"},
            }
        ),
    ):
        with pytest.raises(RuntimeError, match="MCP error -32602"):
            await client.initialize()


@pytest.mark.asyncio
async def test_malformed_http_json_raises_cleanly() -> None:
    client = McpClient("http://localhost:8001")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = httpx.DecodingError("invalid json", request=MagicMock())

    with patch(
        "protocols.mcp.client.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=response,
    ):
        with pytest.raises(httpx.DecodingError):
            await client.initialize()


@pytest.mark.asyncio
async def test_call_get_quote_missing_content() -> None:
    client = MagicMock()
    client.call_tool = AsyncMock(return_value={})

    result = await call_get_quote(client, "AAPL")

    assert result["symbol"] == "AAPL"
    assert result["error"] == "invalid JSON from MCP"


@pytest.mark.asyncio
async def test_call_get_quote_malformed_json_text() -> None:
    client = MagicMock()
    client.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "not json"}]}
    )

    result = await call_get_quote(client, "AAPL")

    assert result["error"] == "invalid JSON from MCP"
    assert result["raw"] == "not json"


@pytest.mark.asyncio
async def test_call_get_quote_yahoo_api_change_missing_price_fields() -> None:
    client = MagicMock()
    client.call_tool = AsyncMock(
        return_value={
            "content": [{"type": "text", "text": '{"symbol":"AAPL","currency":"USD"}'}]
        }
    )

    result = await call_get_quote(client, "AAPL")

    assert result["symbol"] == "AAPL"
    assert "regular_market_price" not in result


@pytest.mark.asyncio
async def test_call_get_quote_passes_through_upstream_error() -> None:
    client = MagicMock()
    client.call_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": '{"error":"missing regularMarketPrice for \'AAPL\'"}',
                }
            ],
            "isError": True,
        }
    )

    result = await call_get_quote(client, "AAPL")

    assert result["symbol"] == "AAPL"
    assert "missing regularMarketPrice" in result["error"]
