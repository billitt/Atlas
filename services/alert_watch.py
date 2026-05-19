"""Async watch loop for Atlas alert rules."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from services.alerts import AlertEngine, AlertResult


class AlertWatcher:
    """Continuously evaluate alert rules at a fixed interval."""

    def __init__(self, alert_engine: AlertEngine, check_interval_seconds: int = 300) -> None:
        self.alert_engine = alert_engine
        self.check_interval_seconds = check_interval_seconds
        self._running = False

    async def start(self) -> None:
        self._running = True
        print(f"[alert_watch] Starting loop every {self.check_interval_seconds}s")
        try:
            while self._running:
                triggered = await self.alert_engine.check_all_rules()
                for alert in triggered:
                    self._on_alert(alert)
                await asyncio.sleep(self.check_interval_seconds)
        except asyncio.CancelledError:
            self.stop()
            raise

    def stop(self) -> None:
        self._running = False
        print("[alert_watch] Stopped")

    def _on_alert(self, alert_result: AlertResult) -> None:
        print(format_alert(alert_result))


def format_alert(alert_result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "",
            "=" * 72,
            f"ATLAS ALERT [{alert_result.get('severity')}] {alert_result.get('rule_name')}",
            "=" * 72,
            f"Triggered: {alert_result.get('triggered_at')}",
            f"Rule ID: {alert_result.get('rule_id')}",
            "",
            "Summary:",
            str(alert_result.get("summary", "")),
            "",
            "Evidence:",
            str(alert_result.get("evidence", "")),
            "",
            "Context:",
            str(alert_result.get("context", "")),
            "",
            "Sources:",
            json.dumps(alert_result.get("sources", []), indent=2)[:3000],
        ]
    )
