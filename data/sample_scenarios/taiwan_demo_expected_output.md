# Taiwan Strait Demo — Expected Output

Reference for interview walkthrough. Actual LLM text varies; structure and data sources should match.

## Prerequisites

- Ollama running with `ibm/granite4.1:8b` and `granite-embedding:278m`
- `cargo run -p mcp-market-data` on `:8001`
- `cargo run -p mcp-edgar` on `:8002`

## Step 1 — Seed ingestion

```
[Step 1] Seed data ingestion
[seed_loader] Ingested 12 seed documents (N total chunks in semantic memory)
Ingested 12 documents into semantic memory
```

Documents ingested:

| ID pattern | Source | Category |
|------------|--------|----------|
| `taiwan-gdelt-*` | `seed_gdelt` | geopolitical |
| `taiwan-gdelt-aggregate` | `seed_gdelt` | geopolitical |
| `taiwan-tsmc-filing-excerpt` | `seed_sec_filing` | filing |
| `taiwan-trade-flow` | `seed_comtrade` | supply_chain |
| `taiwan-chokepoint-*` | `seed_comtrade` | supply_chain |

## Step 2 — Alert (HIGH severity)

```
[Step 2] Real-time alert trigger

ALERT [HIGH] Taiwan Strait tension spike
Triggered: 2026-05-27T...
Summary: Taiwan Strait GDELT aggregate risk_level is HIGH with peak_tone -9.1 over five days.
Evidence: {'five_day_avg_tone': -7.72, 'peak_tone': -9.1, 'risk_level': 'HIGH', ...}
Context: Demo alert evaluated against ingested Taiwan Strait seed GDELT context.
```

Alert rule id: `taiwan_strait_tension`

## Step 3 — Full synthesis query

**Query:** `What's the exposure risk if Taiwan Strait tensions escalate? Consider semiconductor supply chains, market impact, and TSMC filing risk factors.`

**Execution plan** should include four specialist steps:

| Agent | Data source |
|-------|-------------|
| `market` | Live TSMC quote via MCP `:8001` |
| `geopolitical` | Seed GDELT events from semantic memory |
| `supply_chain` | Seed trade flow / chokepoint data from semantic memory |
| `research` | TSMC filings via EDGAR MCP `:8002` (may also match filing excerpt in semantic memory) |

**Expected briefing shape:**

```
Overall confidence: MEDIUM or HIGH
Guardian passed: true/false (MEDIUM/HIGH typical with grounded sources)
trace_id: <32-char hex>

--- Combined analysis (excerpt) ---
[Multi-paragraph synthesis covering:]
- Cross-strait escalation paths and EU/US diplomatic response
- TSMC / advanced chip chokepoint (90% advanced chips from Hsinchu)
- Market price move for TSM
- Filing risk factors (geopolitical exposure, diversification)
- Guardian-validated confidence
```

Run artifact: `runs/YYYYMMDD_HHMMSS.json` with `trace_id`, `agent_results`, `guardian_verdict`.

## Step 4 — Scheduled briefing

```
[Step 4] Scheduled briefing (single topic)
Briefing [custom] topics=1 risk=MEDIUM|HIGH duration=...s
Delta: No prior briefing found for Taiwan Strait semiconductor risk; baseline created at ...
```

First run always shows **baseline created** delta.

## Step 5 — Trace tree

```
[Step 5] Trace exploration

Trace <trace_id> (N spans, ~XXXs)
├── synthesis.run
│   ├── synthesis.plan
│   ├── synthesis.delegate
│   │   ├── a2a.send_task (market)
│   │   │   ├── agent.run (market)
│   │   │   │   ├── agent.plan / agent.execute / agent.reflect
│   │   │   │   └── mcp.tools/call (get_quote)
│   │   ├── a2a.send_task (geopolitical)
│   │   ├── a2a.send_task (supply_chain)
│   │   └── a2a.send_task (research)
│   │       └── mcp.tools/call (company_filings / filing_text)
│   ├── synthesis.synthesize
│   └── guardian.validate
```

Span count typically **25–60** depending on retries and MCP latency.

## Step 6 — Summary box

```
================================================================
        ATLAS TAIWAN STRAIT DEMO — EXERCISED
================================================================
Protocols: MCP (mcp-market-data :8001, mcp-edgar :8002), A2A (4 specialist agents)
Agents: Market, Geopolitical, Supply Chain, Research, Synthesis, Guardian
Memory: Semantic (seed GDELT/trade/filing), Episodic (briefing + alert logged)
Interaction: Alert fired, Query answered, Briefing generated
Observability: trace_id=... spans=N query=...s total=...s
Architecture: Rust MCP data layer + Python intelligence layer + LangGraph orchestration
Also runnable: atlas query "..." | Dashboard Query page (same pipeline)
================================================================
```

## CLI equivalence

After seeding (run demo Step 1 once, or call `load_taiwan_scenario()`):

```bash
atlas query "What's the exposure risk if Taiwan Strait tensions escalate? Consider semiconductor supply chains, market impact, and TSMC filing risk factors."
```

Same LangGraph pipeline; output formatted via `cli/formatters.py`.

## Dashboard equivalence

1. `atlas-api` (and `cd web && npm run dev` for development)
2. Query page → paste the same question → Run
3. Trace Viewer page → open trace by `trace_id` from run log

## Timing (typical local hardware)

| Phase | Duration |
|-------|----------|
| Seed ingestion | ~5–15 s (embeddings) |
| Alert evaluation | ~5–15 s (one Granite call) |
| Full synthesis (4 agents + Guardian) | ~2–6 min |
| Single-topic briefing | ~2–5 min |
| **Total demo** | **~5–12 min** |

Ollama on CPU-only hardware may push toward the upper range.
