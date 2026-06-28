"""Research & Filing Agent backed by the SEC EDGAR MCP server."""

from __future__ import annotations

import json
import re
from typing import Any

from agents.base import AgentResult, BaseAgent, Confidence
from agents.formatting import MARKDOWN_FORMAT_INSTRUCTIONS
from agents.research import tools as research_tools
from memory.semantic import SemanticMemory
from protocols.mcp.client import McpClient
from protocols.mcp.endpoints import mcp_edgar_url
from services.llm import chat

DEFAULT_EDGAR_MCP_URL = mcp_edgar_url()


class ResearchFilingAgent(BaseAgent):
    """Specialist agent for SEC filings and company disclosure research."""

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

    async def setup(self) -> None:
        await research_tools.load_tools(self.mcp)
        print("[research.setup] EDGAR tools loaded")

    async def plan(self, query: str) -> dict[str, Any]:
        prompt = f"""You are the Atlas Research & Filing Agent in the PLAN phase.
Choose SEC EDGAR MCP tools for this query.

Available tools:
{research_tools.format_tools_for_prompt()}

Query: {query}

Rules:
- Output ONLY valid JSON.
- Use company_filings for company-specific SEC filing requests.
- Use filing_text after company_filings when filing content is needed.
- Use full_text_search for broad filing searches.
- Prefer ticker TSM for TSMC ADR, AAPL for Apple, NVDA for Nvidia, ASML for ASML.

JSON schema:
{{
  "tool_calls": [
    {{"tool": "company_filings", "arguments": {{"ticker": "AAPL"}}, "rationale": "why"}}
  ]
}}
"""
        raw = chat(prompt)
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return {
                "tool_calls": [
                    {
                        "tool": "company_filings",
                        "arguments": {"ticker": _fallback_ticker(query)},
                        "rationale": "fallback company lookup",
                    }
                ]
            }

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        fetched: list[dict[str, Any]] = []
        for call in plan.get("tool_calls", []):
            tool = call.get("tool")
            args = call.get("arguments") or {}
            print(f"[research.execute] {tool}({args})")
            if tool == "company_filings":
                filings = await research_tools.call_company_filings(
                    self.mcp,
                    ticker=args.get("ticker"),
                    cik=args.get("cik"),
                )
                fetched.append(
                    {
                        "tool": tool,
                        "arguments": args,
                        "result": filings,
                    }
                )
                if _query_needs_filing_text(query):
                    candidate = _first_periodic_filing(filings)
                    if candidate:
                        cik = args.get("cik") or _cik_for_ticker(args.get("ticker"))
                        if cik:
                            filing_payload = await research_tools.call_filing_text(
                                self.mcp,
                                candidate["accession_number"],
                                cik,
                            )
                            fetched.append(
                                {
                                    "tool": "filing_text",
                                    "arguments": {
                                        "accession_number": candidate["accession_number"],
                                        "cik": cik,
                                    },
                                    "result": filing_payload,
                                }
                            )
                            self._ingest_filing_text(
                                filing_payload,
                                {"accession_number": candidate["accession_number"], "cik": cik},
                            )
            elif tool == "full_text_search":
                fetched.append(
                    {
                        "tool": tool,
                        "arguments": args,
                        "result": await research_tools.call_full_text_search(
                            self.mcp,
                            args.get("query", query),
                            args.get("form_type"),
                            args.get("date_from"),
                        ),
                    }
                )
            elif tool == "filing_text":
                filing_text = await research_tools.call_filing_text(
                    self.mcp,
                    args.get("accession_number", ""),
                    args.get("cik", ""),
                )
                fetched.append({"tool": tool, "arguments": args, "result": filing_text})
                self._ingest_filing_text(filing_text, args)

        prompt = f"""You are the Atlas Research & Filing Agent.
Analyze the SEC filing data below for the user query.

Query: {query}

Fetched EDGAR data:
{json.dumps(fetched, indent=2)[:18000]}

Instructions:
- Ground claims in the filing data provided.
- If only filing metadata is available, say so and avoid quoting unavailable text.
- Identify useful filings, risk-factor language, or disclosure gaps.
- Keep the answer concise and include source references.

{MARKDOWN_FORMAT_INSTRUCTIONS}
"""
        analysis = chat(prompt).strip()
        return {"analysis": analysis, "sources": fetched, "confidence": "MEDIUM"}

    async def reflect(
        self,
        query: str,
        draft: AgentResult,
    ) -> tuple[bool, str, Confidence]:
        prompt = f"""Audit this SEC filing analysis for grounding.

Query: {query}
Sources:
{json.dumps(draft["sources"], indent=2)[:12000]}

Draft:
{draft["analysis"]}

Check:
1. Numbers and filing dates match the source data.
2. The draft does not selectively quote or overstate filing evidence.
3. If filing text is absent, the draft says metadata only was available.

Return ONLY JSON:
{{"passed": true, "confidence": "HIGH|MEDIUM|LOW", "feedback": "short note"}}
"""
        raw = chat(prompt)
        verdict = _parse_json(raw)
        confidence = str(verdict.get("confidence", "LOW")).upper()
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "LOW"
        return bool(verdict.get("passed", False)), str(verdict.get("feedback", "")), confidence  # type: ignore[return-value]

    def _ingest_filing_text(self, filing_payload: dict[str, Any], args: dict[str, Any]) -> None:
        text = filing_payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        accession = str(args.get("accession_number", "unknown"))
        try:
            self.semantic_memory.add_documents(
                texts=[text],
                metadatas=[
                    {"source": "sec_edgar", "accession_number": accession, "cik": args.get("cik")}
                ],
                ids=[f"sec::{accession}"],
            )
            print(f"[research.memory] Ingested filing text into semantic memory: {accession}")
        except Exception as exc:
            print(f"[research.memory] Filing ingestion skipped: {exc}")


def _fallback_ticker(query: str) -> str:
    upper = query.upper()
    if "TSMC" in upper:
        return "TSM"
    if "APPLE" in upper:
        return "AAPL"
    if "NVIDIA" in upper:
        return "NVDA"
    match = re.search(r"\b[A-Z]{1,5}\b", query)
    return match.group(0) if match else "AAPL"


def _query_needs_filing_text(query: str) -> bool:
    lowered = query.lower()
    return any(
        token in lowered for token in ("risk", "disclosure", "md&a", "10-k", "10-q", "filing text")
    )


def _first_periodic_filing(filings: dict[str, Any]) -> dict[str, Any] | None:
    for filing in filings.get("filings", []):
        if filing.get("form_type") in {"10-K", "10-Q", "20-F"}:
            return filing
    return None


def _cik_for_ticker(ticker: str | None) -> str | None:
    if not ticker:
        return None
    ticker_map = {
        "AAPL": "0000320193",
        "TSM": "0001046179",
        "NVDA": "0001045810",
        "ASML": "0000937966",
    }
    return ticker_map.get(ticker.upper())


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
