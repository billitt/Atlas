"""Real-time alert rules over fresh MCP data."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Literal, TypedDict

from agents.guardian.agent import GuardianAgent
from agents.synthesis.agent import SynthesisAgent
from memory.episodic import EpisodicMemory
from observability.run_logger import save_run
from observability.tracing import get_tracer
from protocols.mcp.client import McpClient
from services.llm import chat

Severity = Literal["HIGH", "MEDIUM", "LOW"]
JsonDict = dict[str, Any]
_tracer = get_tracer("services.alerts")


@dataclass
class AlertRule:
    id: str
    name: str
    description: str
    watch_topic: str
    condition_prompt: str
    severity: Severity
    cooldown_seconds: int


class AlertResult(TypedDict):
    rule_id: str
    rule_name: str
    severity: Severity
    triggered_at: str
    summary: str
    evidence: str
    context: str
    sources: list[JsonDict]
    duration_seconds: float


class AlertEngine:
    """Evaluate alert rules and persist triggered results."""

    def __init__(
        self,
        synthesis_agent: SynthesisAgent | None,
        episodic_memory: EpisodicMemory,
        guardian: GuardianAgent | None,
        mcp_client: McpClient | dict[str, McpClient],
    ) -> None:
        self.synthesis_agent = synthesis_agent
        self.episodic_memory = episodic_memory
        self.guardian = guardian or GuardianAgent()
        self.mcp_clients = mcp_client if isinstance(mcp_client, dict) else {"market": mcp_client}
        self.rules: dict[str, AlertRule] = {}
        self._last_fired_at: dict[str, datetime] = {}

    def add_rule(self, rule: AlertRule) -> None:
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        self.rules.pop(rule_id, None)
        self._last_fired_at.pop(rule_id, None)

    def list_rules(self) -> list[AlertRule]:
        return list(self.rules.values())

    async def check_rule(self, rule: AlertRule) -> AlertResult | None:
        with _tracer.start_as_current_span("alerts.check_rule") as span:
            span.set_attribute("rule_id", rule.id)
            span.set_attribute("severity", rule.severity)
            if self._in_cooldown(rule):
                print(f"[alerts] Skipping {rule.id}; cooldown active")
                span.set_attribute("triggered", False)
                return None

            start = perf_counter()
            fresh_data = await self._fresh_data_for_rule(rule)
            verdict = _evaluate_condition(rule, fresh_data)
            triggered = bool(verdict.get("triggered"))
            span.set_attribute("triggered", triggered)
            if not triggered:
                return None

            context = _quick_context(rule, fresh_data, verdict)
            triggered_at = datetime.now().isoformat(timespec="seconds")
            result: AlertResult = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "severity": rule.severity,
                "triggered_at": triggered_at,
                "summary": str(verdict.get("summary", "")).strip(),
                "evidence": str(verdict.get("evidence", "")).strip(),
                "context": context,
                "sources": fresh_data.get("sources", []),
                "duration_seconds": round(perf_counter() - start, 3),
            }
            self._last_fired_at[rule.id] = datetime.now()
            self.episodic_memory.log_alert(result)
            save_run(
                {
                    "timestamp": triggered_at,
                    "query": rule.watch_topic,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "severity": rule.severity,
                    "summary": result["summary"],
                    "evidence": result["evidence"],
                    "sources": result["sources"],
                    "duration_seconds": result["duration_seconds"],
                    "alert_result": result,
                }
            )
            return result

    async def check_all_rules(self) -> list[AlertResult]:
        triggered: list[AlertResult] = []
        for rule in self.rules.values():
            result = await self.check_rule(rule)
            if result is not None:
                triggered.append(result)
        return triggered

    def _in_cooldown(self, rule: AlertRule) -> bool:
        last = self._last_fired_at.get(rule.id)
        if last is None:
            return False
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed < rule.cooldown_seconds

    async def _fresh_data_for_rule(self, rule: AlertRule) -> JsonDict:
        lowered = f"{rule.id} {rule.watch_topic}".lower()
        if "filing" in lowered or "sec" in lowered:
            return await self._filing_activity_data(rule)
        return await self._market_move_data(rule)

    async def _market_move_data(self, rule: AlertRule) -> JsonDict:
        client = self._client("market")
        await client.initialize()
        symbols = _extract_symbols(rule.watch_topic) or ["TSM", "NVDA", "ASML", "SPY"]
        sources = []
        for symbol in symbols:
            raw = await client.call_tool("get_quote", {"symbol": symbol})
            sources.append(
                {"tool": "get_quote", "symbol": symbol, "result": _extract_mcp_json(raw)}
            )
        return {"type": "market", "rule": asdict(rule), "sources": sources}

    async def _filing_activity_data(self, rule: AlertRule) -> JsonDict:
        client = self._client("edgar")
        await client.initialize()
        tickers = _extract_symbols(rule.watch_topic) or ["TSM", "AAPL", "INTC"]
        sources = []
        for ticker in tickers:
            raw = await client.call_tool("company_filings", {"ticker": ticker})
            sources.append(
                {"tool": "company_filings", "ticker": ticker, "result": _extract_mcp_json(raw)}
            )
        return {"type": "filing", "rule": asdict(rule), "sources": sources}

    def _client(self, key: str) -> McpClient:
        client = self.mcp_clients.get(key)
        if client is None:
            raise RuntimeError(f"missing MCP client for {key}")
        return client


def _evaluate_condition(rule: AlertRule, fresh_data: JsonDict) -> JsonDict:
    prompt = f"""You are the Atlas Alert Evaluator.
Decide whether this alert condition is met using only the fresh MCP data.

Rule:
{json.dumps(asdict(rule), indent=2)}

Fresh data:
{json.dumps(fresh_data, indent=2)[:16000]}

Condition:
{rule.condition_prompt}

Return ONLY valid JSON:
{{"triggered": false, "summary": "short summary", "evidence": "specific evidence"}}
"""
    try:
        parsed = _parse_json_from_llm(chat(prompt))
    except json.JSONDecodeError as exc:
        return {
            "triggered": False,
            "summary": "Alert evaluator returned malformed JSON.",
            "evidence": str(exc),
        }
    return {
        "triggered": bool(parsed.get("triggered", False)),
        "summary": str(parsed.get("summary", "")).strip(),
        "evidence": str(parsed.get("evidence", "")).strip(),
    }


def _quick_context(rule: AlertRule, fresh_data: JsonDict, verdict: JsonDict) -> str:
    prompt = f"""Write a concise operational context note for this triggered Atlas alert.
Do not add unsupported facts.

Rule: {rule.name}
Summary: {verdict.get("summary")}
Evidence: {verdict.get("evidence")}
Fresh data:
{json.dumps(fresh_data, indent=2)[:10000]}
"""
    return chat(prompt).strip()


def _extract_mcp_json(raw: JsonDict) -> JsonDict:
    chunks = [
        str(block.get("text", ""))
        for block in raw.get("content", [])
        if block.get("type") == "text"
    ]
    text = "\n".join(chunks).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text, "is_error": bool(raw.get("isError"))}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _extract_symbols(text: str) -> list[str]:
    return re.findall(r"\b[A-Z]{2,5}\b", text)


def _parse_json_from_llm(text: str) -> JsonDict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
        else:
            raise
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("alert evaluator JSON must be an object", text, 0)
    return parsed
