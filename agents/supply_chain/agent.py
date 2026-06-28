"""Supply Chain Agent — live UN Comtrade MCP + ChromaDB cache."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from agents.base import AgentResult, BaseAgent, Confidence
from agents.formatting import MARKDOWN_FORMAT_INSTRUCTIONS
from agents.supply_chain import tools as trade_tools
from memory.semantic import SemanticMemory
from protocols.mcp.client import McpClient
from protocols.mcp.endpoints import mcp_trade_url
from services.llm import chat

DEFAULT_COMTRADE_MCP_URL = mcp_trade_url()

DataMode = Literal["live", "cache", "insufficient"]


class SupplyChainAgent(BaseAgent):
    """Specialist agent for supply-chain risk grounded in live Comtrade trade data."""

    def __init__(
        self,
        mcp_client: McpClient,
        *,
        max_retries: int = 2,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.mcp = mcp_client
        self.semantic_memory = semantic_memory or SemanticMemory()
        self._data_mode: DataMode = "insufficient"
        self._used_cache = False
        self._cache_fetched_at: str | None = None

    async def setup(self) -> None:
        try:
            await trade_tools.load_tools(self.mcp)
            print("[supply_chain.setup] Comtrade tools loaded")
        except Exception as exc:
            print(
                f"[supply_chain.setup] Comtrade MCP unavailable ({exc}); "
                "will use cache or insufficient-data path"
            )

    async def plan(self, query: str) -> dict[str, Any]:
        print("[supply_chain.plan] Deriving Comtrade query parameters...")
        prompt = f"""You are the Atlas Supply Chain Agent in the PLAN phase.
Choose UN Comtrade MCP tools and parameters for supply-chain trade analysis.

Available tools:
{trade_tools.format_tools_for_prompt()}

Query: {query}

Rules:
- Output ONLY valid JSON.
- Use get_trade_data for aggregate trade flows; get_tariffline for tariff-line granularity.
- reporterCode / partnerCode are UN M49 numeric codes (842=USA, 156=China, 158=Taiwan, 276=Germany).
- cmdCode is HS commodity code (8542=electronic integrated circuits / semiconductors).
- flowCode: M=imports, X=exports.
- period is yyyy (e.g. 2022) unless monthly data is explicitly needed.
- Defaults: typeCode=C, freqCode=A, clCode=HS.

JSON schema:
{{
  "tool": "get_trade_data",
  "arguments": {{
    "reporterCode": "842",
    "partnerCode": "156",
    "cmdCode": "8542",
    "flowCode": "M",
    "period": "2022",
    "typeCode": "C",
    "freqCode": "A",
    "clCode": "HS"
  }},
  "rationale": "why these parameters"
}}
"""
        raw = chat(prompt)
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return {
                "tool": "get_trade_data",
                "arguments": {
                    "reporterCode": "842",
                    "partnerCode": "156",
                    "cmdCode": "8542",
                    "flowCode": "M",
                    "period": "2022",
                    "typeCode": "C",
                    "freqCode": "A",
                    "clCode": "HS",
                },
                "rationale": "Fallback: US imports of HS 8542 from China, 2022.",
            }

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        print("[supply_chain.execute] Fetching live Comtrade data...")
        self._data_mode = "insufficient"
        self._used_cache = False
        self._cache_fetched_at = None

        args = plan.get("arguments") or {}
        tool = plan.get("tool", "get_trade_data")
        trade_payload: dict[str, Any] | None = None
        mcp_error: str | None = None

        try:
            if tool == "get_tariffline":
                trade_payload = await trade_tools.call_get_tariffline(
                    self.mcp,
                    reporter_code=str(args.get("reporterCode", "842")),
                    period=str(args.get("period", "2022")),
                    partner_code=args.get("partnerCode"),
                    cmd_code=args.get("cmdCode"),
                    flow_code=args.get("flowCode"),
                    type_code=str(args.get("typeCode", "C")),
                    freq_code=str(args.get("freqCode", "A")),
                    cl_code=str(args.get("clCode", "HS")),
                    max_records=args.get("maxRecords"),
                )
            else:
                trade_payload = await trade_tools.call_get_trade_data(
                    self.mcp,
                    reporter_code=str(args.get("reporterCode", "842")),
                    period=str(args.get("period", "2022")),
                    partner_code=args.get("partnerCode"),
                    cmd_code=args.get("cmdCode"),
                    flow_code=args.get("flowCode"),
                    type_code=str(args.get("typeCode", "C")),
                    freq_code=str(args.get("freqCode", "A")),
                    cl_code=str(args.get("clCode", "HS")),
                    max_records=args.get("maxRecords"),
                )
        except Exception as exc:
            mcp_error = str(exc)
            print(f"[supply_chain.execute] MCP call failed: {exc}")

        if trade_payload and not trade_payload.get("error"):
            rows = trade_payload.get("rows") or []
            count = trade_payload.get("count", 0)
            if count > 0 and rows:
                return self._analyze_live(query, plan, args, tool, trade_payload, rows)

        if trade_payload and trade_payload.get("error"):
            mcp_error = str(trade_payload["error"])

        cache_context, cache_sources, fetched_at = self._cached_comtrade_context(query)
        if cache_context:
            self._data_mode = "cache"
            self._used_cache = True
            self._cache_fetched_at = fetched_at
            return self._analyze_from_context(
                query,
                plan,
                cache_context,
                cache_sources,
                note=(
                    f"Live Comtrade unavailable ({mcp_error or 'no rows returned'}); "
                    f"using cached data from {fetched_at}."
                ),
                confidence="MEDIUM",
            )

        self._data_mode = "insufficient"
        analysis = (
            "## Insufficient trade data\n\n"
            "Live UN Comtrade data could not be retrieved and no prior cached trade records "
            "are available in semantic memory.\n\n"
            f"**Error:** {mcp_error or 'empty response from Comtrade MCP'}\n\n"
            "This assessment cannot quantify trade flows, dependencies, or volumes. "
            "Retry when mcp-trade (:8003) is reachable or after a successful live fetch "
            "populates the cache."
        )
        return {
            "analysis": analysis,
            "sources": [
                {
                    "type": "comtrade_gap",
                    "agent": "supply_chain",
                    "note": "No live Comtrade data and no comtrade_live cache.",
                    "error": mcp_error,
                }
            ],
            "confidence": "LOW",
        }

    def _analyze_live(
        self,
        query: str,
        plan: dict[str, Any],
        args: dict[str, Any],
        tool: str,
        trade_payload: dict[str, Any],
        rows: list[Any],
    ) -> AgentResult:
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        reporter = str(args.get("reporterCode", ""))
        partner = str(args.get("partnerCode", ""))
        cmd = str(args.get("cmdCode", ""))
        period = str(args.get("period", ""))
        doc_id = f"comtrade::{reporter}::{partner}::{cmd}::{period}::{fetched_at}"

        row_text = json.dumps(rows, indent=2)[:12000]
        try:
            self.semantic_memory.add_documents(
                texts=[row_text],
                metadatas=[
                    {
                        "source": "comtrade_live",
                        "reporter": reporter,
                        "partner": partner,
                        "cmd": cmd,
                        "period": period,
                        "fetched_at": fetched_at,
                        "tool": tool,
                    }
                ],
                ids=[doc_id],
            )
            print(f"[supply_chain.memory] Cached {len(rows)} Comtrade rows: {doc_id}")
        except Exception as exc:
            print(f"[supply_chain.memory] Cache write skipped: {exc}")

        self._data_mode = "live"
        self._used_cache = False
        context = json.dumps(trade_payload, indent=2)[:14000]
        sources: list[dict[str, Any]] = [
            {
                "type": "mcp",
                "provider": "mcp-trade",
                "tool": tool,
                "arguments": args,
                "count": trade_payload.get("count"),
                "used_preview": trade_payload.get("used_preview", False),
                "fetched_at": fetched_at,
            }
        ]
        return self._analyze_from_context(
            query,
            plan,
            context,
            sources,
            note="Analysis grounded in live UN Comtrade data fetched this run.",
            confidence="MEDIUM",
        )

    def _analyze_from_context(
        self,
        query: str,
        plan: dict[str, Any],
        context: str,
        sources: list[dict[str, Any]],
        *,
        note: str,
        confidence: Confidence,
    ) -> AgentResult:
        prompt = f"""You are the Atlas Supply Chain Agent.
Analyze supply-chain trade implications using ONLY the Comtrade data below.

Query: {query}
Plan:
{json.dumps(plan, indent=2)}

Comtrade trade data (ONLY source for numeric trade claims):
{context}

Constraints:
- {note}
- Do NOT invent trade volumes, values, or percentages not present in the data above.
- If the data is insufficient for a specific claim, say so explicitly.
- Focus on dependencies, chokepoints, substitution options, lead-time risk, and second-order impacts.

{MARKDOWN_FORMAT_INSTRUCTIONS}
"""
        analysis = chat(prompt).strip()
        return {"analysis": analysis, "sources": sources, "confidence": confidence}

    def _cached_comtrade_context(
        self, query: str
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        try:
            matches = self.semantic_memory.query(query, n_results=8)
        except Exception:
            return "", [], None

        lines: list[str] = []
        sources: list[dict[str, Any]] = []
        fetched_at: str | None = None
        for match in matches:
            metadata = match.get("metadata") or {}
            if metadata.get("source") != "comtrade_live":
                continue
            fa = metadata.get("fetched_at")
            if isinstance(fa, str):
                fetched_at = fa if fetched_at is None else min(fetched_at, fa)
            sources.append(
                {
                    "type": "semantic_memory",
                    "source": "comtrade_live",
                    **metadata,
                    "excerpt": match.get("text", "")[:400],
                }
            )
            lines.append(f"- {match['text']}\n  metadata={metadata}")

        if not lines:
            return "", [], None
        return "\n\n".join(lines), sources, fetched_at

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        print("[supply_chain.reflect] Auditing Comtrade grounding...")
        cache_note = ""
        if self._used_cache and self._cache_fetched_at:
            cache_note = (
                f"\nLive Comtrade was unavailable; analysis used cached data from "
                f"{self._cache_fetched_at}."
            )

        if self._data_mode == "insufficient":
            return (
                False,
                "Insufficient Comtrade data — draft must not invent trade figures.",
                "LOW",
            )

        prompt = f"""You are auditing a supply-chain analysis draft.

Query: {query}
Data mode: {self._data_mode}
Used cache: {self._used_cache}
{cache_note}

Sources:
{json.dumps(draft["sources"], indent=2)[:8000]}

Draft:
{draft["analysis"]}

Check:
1. Numeric trade claims trace to Comtrade data (live or cached).
2. The draft does NOT invent figures when data is missing.
3. If cached data was used, the draft discloses staleness.

Return ONLY valid JSON:
{{
  "passed": true or false,
  "confidence": "HIGH" or "MEDIUM" or "LOW",
  "feedback": "short audit note"
}}
"""
        raw = chat(prompt)
        try:
            verdict = _parse_json(raw)
        except json.JSONDecodeError:
            confidence: Confidence = "LOW" if self._used_cache else "MEDIUM"
            return False, "Reflection did not return valid JSON.", confidence

        confidence = str(verdict.get("confidence", "LOW")).upper()
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "LOW"
        if self._used_cache and confidence == "HIGH":
            confidence = "MEDIUM"
        feedback = str(verdict.get("feedback", ""))
        if self._used_cache:
            feedback = (
                f"{feedback} Live Comtrade unavailable; analysis based on cached data "
                f"from {self._cache_fetched_at}."
            ).strip()
        return bool(verdict.get("passed")), feedback, confidence  # type: ignore[return-value]


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
