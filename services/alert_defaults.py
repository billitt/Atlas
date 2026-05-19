"""Default alert rules for Atlas watch loops."""

from __future__ import annotations

from services.alerts import AlertRule


def default_alert_rules() -> list[AlertRule]:
    return [
        AlertRule(
            id="major_market_move",
            name="Major market move",
            description="Watch semiconductor and broad-market symbols for large daily moves.",
            watch_topic="TSM NVDA ASML SPY semiconductor market watchlist",
            condition_prompt=(
                "Trigger if any quoted symbol has absolute change_percent greater than 5. "
                "Use the MCP quote fields directly."
            ),
            severity="HIGH",
            cooldown_seconds=3600,
        ),
        AlertRule(
            id="filing_activity",
            name="SEC filing activity",
            description="Watch for recent SEC filings from key companies.",
            watch_topic="TSM AAPL INTC SEC filing activity",
            condition_prompt=(
                "Trigger if any watched company has a recent 10-K, 10-Q, 8-K, 20-F, or 6-K "
                "in the returned SEC filing list. Summarize the company, form type, and filing date."
            ),
            severity="MEDIUM",
            cooldown_seconds=7200,
        ),
    ]
