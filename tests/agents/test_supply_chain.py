"""Supply Chain Agent tests — live fetch, cache fallback, insufficient data."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.supply_chain.agent import SupplyChainAgent
from memory.semantic import SemanticMemory
from protocols.mcp.client import McpClient


def _live_payload() -> dict[str, Any]:
    return {
        "count": 1,
        "rows": [{"reporterCode": 842, "cmdCode": "8542", "primaryValue": 1000}],
        "endpoint": "/data/v1/get/C/A/HS",
        "used_preview": False,
    }


@pytest.mark.asyncio
async def test_execute_live_fetches_and_caches() -> None:
    mcp = MagicMock(spec=McpClient)
    mcp.call_tool = AsyncMock(
        return_value={
            "content": [
                {
                    "type": "text",
                    "text": (
                        '{"count": 1, "rows": [{"reporterCode": 842, "primaryValue": 1000}], '
                        '"used_preview": false}'
                    ),
                }
            ]
        }
    )
    memory = MagicMock(spec=SemanticMemory)
    agent = SupplyChainAgent(mcp, semantic_memory=memory)

    with patch("agents.supply_chain.agent.chat", return_value="Live Comtrade analysis with value 1000."):
        result = await agent.execute(
            "US semiconductor imports",
            {
                "tool": "get_trade_data",
                "arguments": {
                    "reporterCode": "842",
                    "period": "2022",
                    "cmdCode": "8542",
                    "flowCode": "M",
                },
            },
        )

    memory.add_documents.assert_called_once()
    assert agent._used_cache is False
    assert agent._data_mode == "live"
    assert result["confidence"] == "MEDIUM"
    assert result["sources"][0]["type"] == "mcp"


@pytest.mark.asyncio
async def test_execute_cache_fallback_when_mcp_fails() -> None:
    mcp = MagicMock(spec=McpClient)
    mcp.call_tool = AsyncMock(side_effect=RuntimeError("connection refused"))
    memory = MagicMock(spec=SemanticMemory)
    memory.query.return_value = [
        {
            "text": '{"rows": [{"primaryValue": 500}]}',
            "metadata": {
                "source": "comtrade_live",
                "fetched_at": "2024-01-01T00:00:00+00:00",
            },
        }
    ]
    agent = SupplyChainAgent(mcp, semantic_memory=memory)

    with patch("agents.supply_chain.agent.chat", return_value="Cached trade analysis."):
        result = await agent.execute(
            "US semiconductor imports",
            {"tool": "get_trade_data", "arguments": {"reporterCode": "842", "period": "2022"}},
        )

    assert agent._used_cache is True
    assert agent._data_mode == "cache"
    assert result["confidence"] == "MEDIUM"
    assert "cached" in result["sources"][0].get("source", "") or any(
        s.get("source") == "comtrade_live" for s in result["sources"]
    )


@pytest.mark.asyncio
async def test_execute_insufficient_when_no_live_or_cache() -> None:
    mcp = MagicMock(spec=McpClient)
    mcp.call_tool = AsyncMock(return_value={"content": [{"type": "text", "text": '{"error": "down"}'}], "isError": True})
    memory = MagicMock(spec=SemanticMemory)
    memory.query.return_value = []
    agent = SupplyChainAgent(mcp, semantic_memory=memory)

    result = await agent.execute(
        "US semiconductor imports",
        {"tool": "get_trade_data", "arguments": {"reporterCode": "842", "period": "2022"}},
    )

    assert agent._data_mode == "insufficient"
    assert result["confidence"] == "LOW"
    assert "Insufficient trade data" in result["analysis"]
    memory.add_documents.assert_not_called()


@pytest.mark.asyncio
async def test_reflect_downgrades_cache_confidence() -> None:
    mcp = MagicMock(spec=McpClient)
    agent = SupplyChainAgent(mcp)
    agent._data_mode = "cache"
    agent._used_cache = True
    agent._cache_fetched_at = "2024-01-01T00:00:00+00:00"
    draft = {
        "analysis": "Cached analysis.",
        "sources": [{"type": "semantic_memory", "source": "comtrade_live"}],
        "confidence": "MEDIUM",
    }

    with patch(
        "agents.supply_chain.agent.chat",
        return_value='{"passed": true, "confidence": "HIGH", "feedback": "ok"}',
    ):
        passed, feedback, confidence = await agent.reflect("query", draft)

    assert passed is True
    assert confidence == "MEDIUM"
    assert "cached data" in feedback.lower()


@pytest.mark.asyncio
async def test_reflect_insufficient_forces_low() -> None:
    mcp = MagicMock(spec=McpClient)
    agent = SupplyChainAgent(mcp)
    agent._data_mode = "insufficient"
    draft = {
        "analysis": "Some guess.",
        "sources": [],
        "confidence": "LOW",
    }

    passed, _, confidence = await agent.reflect("query", draft)

    assert passed is False
    assert confidence == "LOW"
