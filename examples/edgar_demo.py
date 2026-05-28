"""Phase 6 demo: SEC EDGAR MCP server + Research/Filing Agent."""

from __future__ import annotations

import asyncio
import json
import sys

from agents.research.agent import DEFAULT_EDGAR_MCP_URL, ResearchFilingAgent
from agents.research.tools import call_company_filings, call_filing_text, load_tools
from protocols.mcp.client import McpClient


async def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Atlas EDGAR Demo (Phase 6)")
    print("Prerequisite: Rust mcp-edgar server running on http://localhost:8002")
    print("-" * 72)

    client = McpClient(DEFAULT_EDGAR_MCP_URL, timeout=180.0)
    tools = await load_tools(client)
    print("EDGAR MCP tools:")
    for tool in tools:
        print(f"  - {tool.get('name')}: {tool.get('description')}")

    filings = await call_company_filings(client, ticker="AAPL")
    print("\nRecent AAPL filings:")
    print(json.dumps(filings, indent=2)[:3000])

    first = next(
        (
            filing
            for filing in filings.get("filings", [])
            if filing.get("form_type") in {"10-K", "10-Q"}
        ),
        None,
    )
    if first:
        text = await call_filing_text(
            client,
            first["accession_number"],
            "0000320193",
        )
        print("\nFirst filing text preview:")
        print(str(text.get("text", ""))[:1000])

    agent = ResearchFilingAgent(client)
    await agent.setup()
    result = await agent.run("Summarize recent AAPL SEC filings and identify risk disclosures.")
    print("\nResearch Agent result:")
    print(json.dumps(result, indent=2)[:6000])


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
