"""Tests for query route source normalization (UI labels)."""

from __future__ import annotations

from api.routes.query import _normalize_source, _normalize_sources


def test_live_comtrade_mcp_source() -> None:
    result = _normalize_source(
        {
            "type": "mcp",
            "provider": "mcp-trade",
            "tool": "get_trade_data",
            "arguments": {"reporterCode": "490", "partnerCode": "842"},
            "count": 1,
            "fetched_at": "2026-06-29T00:02:43+00:00",
        }
    )
    assert result is not None
    assert result["label"] == "UN Comtrade (live)"
    assert "Get trade data" in (result.get("detail") or "")


def test_cached_comtrade_not_labeled_edgar() -> None:
    """Regression: cache sources include tool=get_trade_data from Chroma metadata."""
    result = _normalize_source(
        {
            "type": "semantic_memory",
            "source": "comtrade_live",
            "tool": "get_trade_data",
            "reporter": "490",
            "partner": "842",
            "period": "2024",
            "fetched_at": "2026-06-28T12:00:00+00:00",
            "excerpt": '{"primaryValue": 4510000000}',
        }
    )
    assert result is not None
    assert result["label"] == "UN Comtrade (cached)"
    assert "SEC EDGAR" not in result["label"]
    assert result.get("detail") == "(cached 2026-06-28)"


def test_cached_comtrade_period_fallback_detail() -> None:
    result = _normalize_source(
        {
            "type": "semantic_memory",
            "source": "comtrade_live",
            "tool": "get_trade_data",
            "period": "2022",
        }
    )
    assert result is not None
    assert result["label"] == "UN Comtrade (cached)"
    assert result.get("detail") == "period 2022"


def test_edgar_company_filings_source() -> None:
    result = _normalize_source(
        {
            "tool": "company_filings",
            "arguments": {"ticker": "AAPL"},
            "result": {"filings": []},
        }
    )
    assert result is not None
    assert result["label"] == "SEC EDGAR — Company filings (AAPL)"


def test_edgar_unknown_tool_with_result_payload() -> None:
    result = _normalize_source(
        {
            "tool": "future_edgar_tool",
            "arguments": {"ticker": "TSM"},
            "result": {"data": []},
        }
    )
    assert result is not None
    assert result["label"] == "SEC EDGAR — Future edgar tool (TSM)"


def test_market_quote_symbol_first() -> None:
    result = _normalize_source(
        {
            "type": "mcp",
            "server": "mcp-market-data",
            "tool": "get_quote",
            "symbol": "TSM",
            "provider": "Yahoo Finance (via query1.finance.yahoo.com)",
        }
    )
    assert result is not None
    assert result["label"] == "TSM"
    assert "Yahoo Finance" in (result.get("detail") or "")


def test_normalize_sources_deduplicates() -> None:
    raw = [
        {"type": "mcp", "provider": "mcp-trade", "tool": "get_trade_data"},
        {"type": "mcp", "provider": "mcp-trade", "tool": "get_trade_data"},
    ]
    out = _normalize_sources(raw)
    assert len(out) == 1
