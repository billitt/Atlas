# Atlas Agents

Reference for each agent in the system: responsibility, data connections, reflection behavior, and Agent Card skills.

---

## Shared Pattern: BaseAgent

All specialist agents implement:

```text
run(query) → plan → execute → reflect → (retry if reflect fails)
```

| Phase | LLM role | Output |
|-------|----------|--------|
| Plan | Structured JSON plan | Dimensions, entities, rationale |
| Execute | Analysis with data context | `AgentResult`: analysis, sources, confidence |
| Reflect | Audit draft | pass/fail, feedback, adjusted confidence |

Confidence levels: `HIGH`, `MEDIUM`, `LOW`.

---

## Market Intelligence Agent

**Port:** `:9001`  
**Module:** `agents/market/agent.py`

### Responsibility

Live market analysis: equities, commodities, forex. Fetches quotes via MCP, enriches with semantic memory context, produces grounded price/volume analysis.

### MCP connections

| Server | Tool | Purpose |
|--------|------|---------|
| `mcp-market-data` :8001 | `get_quote` | Yahoo Finance price, change, volume baselines |

### Reflection

Checks that claims trace to MCP quote data; flags unsupported price assertions.

### Agent Card skills

| Skill ID | Description |
|----------|-------------|
| `market_snapshot` | Current price, change, volume for symbols |
| `anomaly_scan` | Unusual price or volume movements |
| `correlation_check` | Cross-asset correlation |

---

## Geopolitical Risk Agent

**Port:** `:9002`  
**Module:** `agents/geopolitical/agent.py`

### Responsibility

Geopolitical escalation paths, sanctions, trade exposure, second-order market effects.

### Data connections

- **Live MCP:** Not yet built (future GDELT MCP)
- **Semantic memory:** Queries ChromaDB for seed GDELT-style events when Taiwan scenario is ingested
- **Fallback:** Granite model knowledge with explicit limitation disclosure

### Reflection

Ensures limitation disclosure when no seed context; validates seed-grounded claims when context exists.

### Agent Card skills

| Skill ID | Description |
|----------|-------------|
| `risk_assessment` | Regional conflict and escalation analysis |
| `sanctions_scan` | Export control and sanctions exposure |
| `trade_exposure` | Cross-border trade disruption risk |

---

## Supply Chain Agent

**Port:** `:9003`  
**Module:** `agents/supply_chain/agent.py`

### Responsibility

Supply-chain dependencies, chokepoints, substitution options, lead-time risk.

### Data connections

| Server | Tool | Purpose |
|--------|------|---------|
| `mcp-trade` :8003 | `get_trade_data` | UN Comtrade bilateral trade flows |
| | `get_tariffline` | Tariff-line granularity |
| | `preview_trade` | Keyless preview (500 record cap) |

- **Semantic memory:** Caches live Comtrade rows (`source=comtrade_live`); no trade-flow seed ingestion
- **Fallback:** If MCP unavailable at startup, agent continues with cache + model knowledge and explicit LOW confidence disclosure

### Reflection

Checks that trade claims trace to Comtrade MCP or cached `comtrade_live` context; flags model-only answers without disclosure.

### Agent Card skills

| Skill ID | Description |
|----------|-------------|
| `dependency_map` | Critical inputs and supplier dependencies |
| `chokepoint_analysis` | Single points of failure in logistics |
| `substitution_risk` | Alternative sourcing feasibility |

---

## Research & Filing Agent

**Port:** `:9004`  
**Module:** `agents/research/agent.py`

### Responsibility

SEC filing retrieval, risk factor extraction, financial disclosure analysis.

### MCP connections

| Server | Tool | Purpose |
|--------|------|---------|
| `mcp-edgar` :8002 | `company_filings` | Recent filings for ticker/CIK |
| | `filing_text` | Full filing document text |
| | `full_text_search` | SEC full-text search index |

### Semantic memory

Ingests filing text chunks after fetch (`source=sec_edgar`, accession metadata).

### Reflection

Checks that filing claims reference retrieved documents; avoids inventing SEC content.

### Agent Card skills

| Skill ID | Description |
|----------|-------------|
| `filing_summary` | Summarize recent 10-K/10-Q/20-F filings |
| `financial_extract` | Extract key financial metrics |
| `filing_diff` | Compare filing changes over time |

---

## Guardian Agent

**Port:** `:9005` (Agent Card reserved; runs in-graph, not as standalone A2A server)  
**Module:** `agents/guardian/agent.py`

### Why Guardian doesn't generate content

Guardian is a **validator**, not an analyst. Separation of concerns (ADR-007):

- **Specialists** gather and analyze
- **Synthesis** merges into a briefing
- **Guardian** checks grounding, flags speculative language, assigns per-claim confidence

Guardian never rewrites the briefing. It returns a `GuardianVerdict`: `passed`, `overall_confidence`, `claim_checks`, `flags`, `summary`.

If `overall_confidence == LOW` and retries remain, LangGraph routes back to synthesize with Guardian feedback.

### Agent Card skills

| Skill ID | Description |
|----------|-------------|
| `validate` | Claim grounding and source freshness audit |
| `confidence_score` | Per-claim and overall confidence calibration |

---

## Synthesis Agent

**Module:** `agents/synthesis/agent.py`  
**Planner:** `agents/synthesis/planner.py`

### Responsibility

Orchestrates multi-agent workflows: creates execution plan, delegates via A2A, merges results, produces unified briefing.

### DAG planner

`create_execution_plan(query, agent_cards)` returns:

```json
{
  "steps": [
    {"agent": "market", "task": "...", "depends_on": []},
    {"agent": "geopolitical", "task": "...", "depends_on": []},
    {"agent": "supply_chain", "task": "...", "depends_on": ["geopolitical"]},
    {"agent": "research", "task": "...", "depends_on": []}
  ],
  "rationale": "..."
}
```

Granite selects specialists based on query keywords and Agent Card skills. Guardian steps are filtered out — Guardian runs as a graph node after synthesis.

### Episodic memory

Queries similar past briefings before synthesizing; logs new briefing records after completion.

### Does not use BaseAgent

Synthesis has its own `plan → delegate → synthesize` flow orchestrated by LangGraph, not the reflect loop.

---

## Agent Discovery

Agent Cards live in `agents/*/agent_card.json`. `protocols/a2a/discovery.py` loads them at startup. Demos and CLI auto-start A2A servers via `examples/_demo_infra.py`.

---

## Related Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — system overview
- [PROTOCOLS.md](PROTOCOLS.md) — A2A delegation details
- [DATA_SOURCES.md](DATA_SOURCES.md) — MCP server reference
