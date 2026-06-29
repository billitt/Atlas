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

# Comtrade reports Taiwan under M49 490 ("Other Asia, nes"), not ISO 158.
_COUNTRY_M49: dict[str, str] = {
    "taiwan": "490",
    "tsmc": "490",
    "hsinchu": "490",
    "china": "156",
    "prc": "156",
    "united states": "842",
    "u.s.": "842",
    "us ": "842",
    "usa": "842",
    "america": "842",
    "germany": "276",
    "japan": "392",
    "korea": "410",
    "south korea": "410",
    "netherlands": "528",
    "asml": "528",
    "world": "0",
    "global": "0",
}

# Map product keywords to HS commodity codes.
_HS_KEYWORDS: dict[str, str] = {
    "processor": "854231",
    "cpu": "854231",
    "gpu": "854231",
    "integrated circuit": "8542",
    "semiconductor": "8542",
    "chip": "8542",
    "wafer": "8542",
    "logic": "8542",
    "memory": "8542",
    "semiconductor device": "8541",
    "diode": "8541",
    "transistor": "8541",
}


def _latest_comtrade_year() -> str:
    """Latest annual year that UN Comtrade is likely to have published.

    Comtrade annual data lags ~12-18 months, so default to two years back
    rather than the current calendar year.
    """
    return str(datetime.now(timezone.utc).year - 2)


def _match_country_codes(query: str) -> list[str]:
    """Return M49 codes for any country keywords found in the query, in order."""
    lowered = query.lower()
    codes: list[str] = []
    for keyword, code in _COUNTRY_M49.items():
        if keyword in lowered and code not in codes:
            codes.append(code)
    return codes


def _match_commodity_code(query: str) -> str:
    """Return the HS code for the first product keyword found, default 8542."""
    lowered = query.lower()
    for keyword, code in _HS_KEYWORDS.items():
        if keyword in lowered:
            return code
    return "8542"


def _fallback_plan_from_query(query: str) -> dict[str, Any]:
    """Query-derived plan when the planning LLM returns malformed JSON.

    Mirrors the Market agent's `_fallback_symbol_from_query`: derive parameters
    from the user query instead of hardcoding a fixed country/commodity/year.
    """
    countries = _match_country_codes(query)
    cmd_code = _match_commodity_code(query)

    # Partner is the non-reporter country of interest; reporter defaults to World
    # so a single named country (e.g. Taiwan) is treated as the trade partner.
    if len(countries) >= 2:
        reporter_code, partner_code = countries[0], countries[1]
    elif len(countries) == 1:
        reporter_code, partner_code = "0", countries[0]
    else:
        reporter_code, partner_code = "0", None

    arguments: dict[str, Any] = {
        "reporterCode": reporter_code,
        "cmdCode": cmd_code,
        "flowCode": "M",
        "period": _latest_comtrade_year(),
        "typeCode": "C",
        "freqCode": "A",
        "clCode": "HS",
    }
    if partner_code is not None:
        arguments["partnerCode"] = partner_code

    return {
        "tool": "get_trade_data",
        "arguments": arguments,
        "rationale": "Fallback plan derived from country/product keywords in the query.",
    }


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
        latest_year = _latest_comtrade_year()
        prompt = f"""You are the Atlas Supply Chain Agent in the PLAN phase.
Derive the UN Comtrade query parameters that best answer THIS user query.
Do not copy the schema values; reason about the countries and products the
query is actually about and translate them into codes.

Available tools:
{trade_tools.format_tools_for_prompt()}

User query: {query}

How to choose parameters:
- Identify the countries/regions and products named or implied in the query,
  then map them to UN M49 country codes and HS commodity codes.
- reporterCode / partnerCode are UN M49 numeric codes. Reference:
  842=USA, 156=China, 490=Taiwan (Comtrade reports Taiwan as "Other Asia, nes"),
  276=Germany, 392=Japan, 410=South Korea, 528=Netherlands, 0=World.
  Note: Taiwan is 490 in Comtrade, NOT 158.
- DIRECTIONALITY (critical): reporterCode is the country whose trade is being
  measured — for an import/dependency query, this is the IMPORTING country (the
  one doing the depending). partnerCode is the counterpart — the SOURCE country
  the imports come FROM.
- Read the query as "how dependent is X on imports from Y": reporterCode = X
  (the importer), partnerCode = Y (the source), flowCode = M.
- Example: "How dependent is the US on Taiwan semiconductor imports" =>
  reporterCode 842 (US, the importer), partnerCode 490 (Taiwan, the source),
  cmdCode 8542, flowCode M.
- If the query names no importing country and asks about a single source country
  in general (e.g. "global reliance on Taiwan chips"), use reporterCode 0 (World)
  and partnerCode = that source country.
- cmdCode is an HS commodity code. Reference:
  8542=electronic integrated circuits / semiconductors, 8541=semiconductor
  devices (diodes/transistors), 854231=processors and controllers.
- flowCode by intent: imports / dependency => M; export reliance => X.
- period: request the latest available annual year. Comtrade annual data lags
  ~12-18 months, so use "{latest_year}" unless the query names a specific year.
- Defaults: typeCode=C, freqCode=A, clCode=HS.
- Use get_trade_data for aggregate trade flows; get_tariffline for tariff-line
  granularity.

Output ONLY valid JSON in this shape (values below are PLACEHOLDERS — replace
them with codes derived from the query, do not echo them):
{{
  "tool": "get_trade_data",
  "arguments": {{
    "reporterCode": "<M49 reporter>",
    "partnerCode": "<M49 partner>",
    "cmdCode": "<HS code>",
    "flowCode": "M or X",
    "period": "{latest_year}",
    "typeCode": "C",
    "freqCode": "A",
    "clCode": "HS"
  }},
  "rationale": "how the query maps to these codes"
}}
"""
        raw = chat(prompt)
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return _fallback_plan_from_query(query)

    async def execute(self, query: str, plan: dict[str, Any]) -> AgentResult:
        print("[supply_chain.execute] Fetching live Comtrade data...")
        self._data_mode = "insufficient"
        self._used_cache = False
        self._cache_fetched_at = None

        args = plan.get("arguments") or {}
        tool = plan.get("tool", "get_trade_data")
        mcp_error: str | None = None

        # Comtrade annual data lags, so try the requested (or latest) year and
        # step back up to two earlier years if the year has no published rows yet.
        requested_period = str(args.get("period") or _latest_comtrade_year())
        candidate_years = self._candidate_years(requested_period)

        for year in candidate_years:
            try:
                payload = await self._fetch_trade(tool, args, year)
            except Exception as exc:
                mcp_error = str(exc)
                print(f"[supply_chain.execute] MCP call failed: {exc}")
                break

            if payload.get("error"):
                mcp_error = str(payload["error"])
                break

            rows = payload.get("rows") or []
            count = payload.get("count", 0)
            if count > 0 and rows:
                # Record the year actually used so sources/cache reflect it.
                args["period"] = year
                return self._analyze_live(query, plan, args, tool, payload, rows)
            print(f"[supply_chain.execute] No Comtrade rows for period {year}; stepping back")

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

    @staticmethod
    def _candidate_years(period: str) -> list[str]:
        """Requested year plus up to two earlier years, for annual-data lag.

        Monthly periods (yyyymm) or non-numeric periods are used as-is.
        """
        if len(period) == 4 and period.isdigit():
            start = int(period)
            return [str(start), str(start - 1), str(start - 2)]
        return [period]

    async def _fetch_trade(
        self, tool: str, args: dict[str, Any], period: str
    ) -> dict[str, Any]:
        """Run one Comtrade MCP call for the given tool and period."""
        common = {
            "reporter_code": str(args.get("reporterCode", "0")),
            "period": period,
            "partner_code": args.get("partnerCode"),
            "cmd_code": args.get("cmdCode"),
            "flow_code": args.get("flowCode"),
            "type_code": str(args.get("typeCode", "C")),
            "freq_code": str(args.get("freqCode", "A")),
            "cl_code": str(args.get("clCode", "HS")),
            "max_records": args.get("maxRecords"),
        }
        if tool == "get_tariffline":
            return await trade_tools.call_get_tariffline(self.mcp, **common)
        return await trade_tools.call_get_trade_data(self.mcp, **common)

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
