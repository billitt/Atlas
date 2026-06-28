"""Market Intelligence Agent — MCP market data + Granite reasoning + reflection."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence
from agents.formatting import MARKDOWN_FORMAT_INSTRUCTIONS
from agents.market import tools as market_tools
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from protocols.mcp.client import McpClient
from services.llm import chat

DEFAULT_MCP_URL = "http://localhost:8001"


def _parse_json_from_llm(text: str) -> dict[str, Any]:
    """Extract a JSON object from model output (raw or ```json fenced)."""
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


def _fallback_symbol_from_query(query: str) -> str:
    """Conservative fallback when the planning LLM returns malformed JSON."""
    query_upper = query.upper()
    if "TSMC" in query_upper:
        return "TSM"

    tickers = re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b", query)
    return tickers[0] if tickers else "AAPL"


class MarketIntelligenceAgent(BaseAgent):
    """Fetches live quotes via Rust MCP, analyzes with Granite, self-reflects before answering."""

    def __init__(
        self,
        mcp_client: McpClient,
        *,
        max_retries: int = 2,
        mcp_server_name: str = "mcp-market-data",
        semantic_memory: SemanticMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self.mcp = mcp_client
        self.mcp_server_name = mcp_server_name
        self._reflection_feedback = ""
        self.semantic_memory = semantic_memory or SemanticMemory()
        self.episodic_memory = episodic_memory or EpisodicMemory()

    async def setup(self) -> None:
        """Load tool definitions from the MCP server (call once before run)."""
        await market_tools.load_tools(self.mcp)
        print(f"[setup] MCP tools: {', '.join(market_tools.tool_names()) or '(none)'}")

    async def plan(self, query: str) -> list[dict[str, Any]]:
        """LLM call #1 — choose MCP tool invocations from the user question."""
        feedback_block = ""
        if self._reflection_feedback:
            feedback_block = f"""
Previous reflection said the last answer was not good enough:
{self._reflection_feedback}

Adjust your tool plan if needed (e.g. different ticker symbol).
"""

        prompt = f"""You are the Atlas Market Intelligence Agent in the PLAN phase.
Given a user question about financial markets, decide which MCP tools to call.

Available MCP tools (from tools/list):
{market_tools.format_tools_for_prompt()}

User question: {query}
{feedback_block}

Rules:
- Output ONLY valid JSON, no markdown fences.
- Use Yahoo Finance ticker symbols (e.g. AAPL, TSM for Taiwan Semiconductor, 2330.TW for Taiwan listing).
- For semiconductor or Taiwan Strait market-impact queries, prefer valid liquid Yahoo symbols such as TSM, NVDA, ASML, SMH, SOXX, and SPY.
- Avoid ambiguous, index-only, or delisted symbols such as SOX and MXIM unless the user explicitly asks for them.
- Only request tools that exist in the list above.
- For "what's happening with X stock" questions, usually call get_quote once per symbol.

JSON schema:
{{
  "tool_calls": [
    {{"tool": "get_quote", "arguments": {{"symbol": "TSM"}}, "rationale": "why this symbol"}}
  ]
}}
"""
        raw = chat(prompt)
        try:
            parsed = _parse_json_from_llm(raw)
        except json.JSONDecodeError:
            symbol = _fallback_symbol_from_query(query)
            print(f"[plan] Could not parse Granite JSON plan; falling back to get_quote({symbol})")
            parsed = {
                "tool_calls": [
                    {
                        "tool": "get_quote",
                        "arguments": {"symbol": symbol},
                        "rationale": "fallback ticker extracted from the user query",
                    }
                ]
            }

        calls = parsed.get("tool_calls", [])
        if not isinstance(calls, list):
            raise ValueError(f"plan phase returned invalid tool_calls: {parsed!r}")
        print(f"[plan] Granite selected {len(calls)} tool call(s)")
        for call in calls:
            print(
                f"       -> {call.get('tool')}({call.get('arguments')}) - {call.get('rationale', '')}"
            )
        return calls

    async def execute(self, query: str, plan: list[dict[str, Any]]) -> AgentResult:
        """MCP fetches + LLM call #2 — analyze real quote data."""
        sources: list[dict[str, Any]] = []
        fetched_blocks: list[str] = []

        for call in plan:
            tool_name = call.get("tool")
            arguments = call.get("arguments") or {}
            if tool_name != "get_quote":
                print(f"[execute] Skipping unknown tool: {tool_name}")
                continue

            symbol = str(arguments.get("symbol", "")).strip()
            print(f"[execute] MCP get_quote(symbol={symbol!r})...")
            quote = await market_tools.call_get_quote(self.mcp, symbol)

            source = {
                "type": "mcp",
                "server": self.mcp_server_name,
                "tool": "get_quote",
                "symbol": symbol,
                "endpoint": f"{self.mcp.base_url}/mcp",
                "provider": "Yahoo Finance (via query1.finance.yahoo.com)",
                "data": quote,
            }
            sources.append(source)
            fetched_blocks.append(json.dumps({"symbol": symbol, "quote": quote}, indent=2))

        data_section = "\n\n".join(fetched_blocks) if fetched_blocks else "(no data fetched)"
        semantic_context = self._semantic_context(query)
        correction_block = ""
        if self._reflection_feedback:
            correction_block = f"""

Previous reflection feedback to fix in this draft:
{self._reflection_feedback}
"""

        prompt = f"""You are the Atlas Market Intelligence Agent in the ANALYZE phase.
Answer the user's question using ONLY the market data below. Do not invent any information not provided in the market data.

User question: {query}

Market data (from MCP / Yahoo Finance):
{data_section}

Relevant semantic memory context:
{semantic_context}
{correction_block}

Write a concise analyst-style answer that:
- States current price, change vs previous close, and volume when available
- Notes currency and any data gaps or errors explicitly
- Does not claim or speculate about news, earnings, macro events, sentiment, or causes of price movement unless present in the data
- Uses previous_day_volume, average_volume_5d, and volume_vs_average_percent when present to compare volume
- Reports volume as a raw share count only if no volume benchmark fields are present
- Do not infer causes, directional pressure, participation quality, or investor intent from quote fields alone
- If the data only contains quote and volume fields, say it shows price/volume movement but not the reason

End with a single line: SOURCES: comma-separated list of symbols you used.

{MARKDOWN_FORMAT_INSTRUCTIONS}
"""
        analysis = chat(prompt).strip()
        print("[execute] Granite draft analysis complete")

        return {
            "analysis": analysis,
            "sources": sources,
            "confidence": "MEDIUM",
        }

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        """LLM call #3 — critique grounding; retry loop uses feedback if this fails."""
        data_blob = json.dumps(draft["sources"], indent=2)
        prompt = f"""You are the Atlas Market Intelligence Agent in the REFLECT phase.
Your job is to audit whether the draft analysis is grounded in the fetched data.

User question: {query}

Fetched source data (JSON):
{data_blob}

Draft analysis:
{draft["analysis"]}

Check:
1. Every numeric claim (price, %, volume) appears in the source data.
2. No fabricated or speculative news, earnings, sentiment, macro narrative, causes, pressure, or investor intent.
3. Volume comparisons are based only on previous_day_volume, average_volume_5d, or volume_vs_average_percent when those fields exist.
4. Errors or missing fields in source data are acknowledged, not hidden.

Respond with ONLY valid JSON (no markdown):
{{
  "passed": true or false,
  "confidence": "HIGH" or "MEDIUM" or "LOW",
  "feedback": "short explanation — what is wrong if passed is false, or why it is grounded if true"
}}
"""
        raw = chat(prompt)
        verdict = _parse_json_from_llm(raw)

        passed = bool(verdict.get("passed", False))
        confidence = _normalize_confidence(verdict.get("confidence", "LOW"))
        feedback = str(verdict.get("feedback", "no feedback provided"))

        self._reflection_feedback = feedback
        return passed, feedback, confidence

    async def run(self, query: str) -> AgentResult:
        """Override to stash reflection feedback between retries for replanning."""
        self._reflection_feedback = ""
        start = perf_counter()
        result = await super().run(query)
        duration = round(perf_counter() - start, 3)
        try:
            self.episodic_memory.log_agent_execution(
                agent_name="market",
                task=query,
                result=result,
                confidence=result["confidence"],
                duration=duration,
            )
            print("[market.memory] Logged agent execution to episodic memory")
        except Exception as exc:
            print(f"[market.memory] Episodic logging skipped: {exc}")
        return result

    def _semantic_context(self, query: str) -> str:
        try:
            if self.semantic_memory.count() == 0:
                return "(no semantic memory documents stored)"
            matches = self.semantic_memory.query(query, n_results=3)
        except Exception as exc:
            return f"(semantic memory unavailable: {exc})"

        if not matches:
            return "(no relevant semantic memory matches)"
        return "\n\n".join(
            f"- {match['text']}\n  metadata={match['metadata']} distance={match['distance']}"
            for match in matches
        )


def _normalize_confidence(value: str) -> Confidence:
    upper = str(value).upper().strip()
    if upper in ("HIGH", "MEDIUM", "LOW"):
        return upper  # type: ignore[return-value]
    return "LOW"
