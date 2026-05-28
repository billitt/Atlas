# Atlas Data Sources

MCP servers, external APIs, seed data, and agent mappings.

---

## MCP Servers

### mcp-market-data (port 8001)

| Property | Value |
|----------|-------|
| **Language** | Rust (Axum) |
| **External API** | Yahoo Finance chart API |
| **Auth** | None (public API) |
| **Rate limits** | Yahoo unofficial limits apply; no explicit Atlas throttle |
| **Start** | `cd rust && cargo run -p mcp-market-data` |

**Tools:**

| Tool | Input | Output |
|------|-------|--------|
| `get_quote` | `symbol: str` | Price, previous close, change %, volume vs 5-day average |

**Used by:** Market Intelligence Agent (`:9001`), AlertEngine (market move rules)

---

### mcp-edgar (port 8002)

| Property | Value |
|----------|-------|
| **Language** | Rust (Axum) |
| **External API** | SEC EDGAR (submissions, archives, full-text search) |
| **Auth** | None; requires valid `User-Agent` header |
| **Rate limits** | SEC fair access: 125 ms delay between requests (`sec_delay()`) |
| **Start** | `cd rust && cargo run -p mcp-edgar` |

**Tools:**

| Tool | Input | Output |
|------|-------|--------|
| `company_filings` | `ticker` or `cik` | Recent filing summaries |
| `filing_text` | `cik`, `accession_number` | Full filing HTML (stripped to text) |
| `full_text_search` | `query`, optional filters | SEC EFTS search results |

**Used by:** Research & Filing Agent (`:9004`), AlertEngine (filing activity rules)

**API endpoints:**

- `https://www.sec.gov/files/company_tickers.json`
- `https://data.sec.gov/submissions/CIK##########.json`
- `https://www.sec.gov/Archives/edgar/data/...`
- `https://efts.sec.gov/LATEST/search-index`

---

## Agent → Data Source Map

| Agent | Live MCP | Semantic Memory | Model Knowledge |
|-------|----------|-----------------|-----------------|
| Market | `get_quote` (:8001) | Prior analyses, context | — |
| Geopolitical | — (future GDELT MCP) | Seed GDELT events | Fallback with disclosure |
| Supply Chain | — (future Comtrade MCP) | Seed trade flow | Fallback with disclosure |
| Research | EDGAR tools (:8002) | Ingested filing chunks | — |
| Synthesis | — | Similar past briefings (episodic) | Planning + merge |
| Guardian | — | — | Validation only |

---

## Seed Data (Taiwan Strait Demo)

Simulated data ingested via `ingestion/seed_loader.py` → ChromaDB semantic memory.

| File | Simulates | Category | Key entities |
|------|-----------|----------|--------------|
| `data/seed_data/taiwan_scenario.json` | GDELT conflict events | geopolitical | Taiwan, China, TSMC, ASML, South China Sea |
| `data/seed_data/trade_flow_data.json` | UN Comtrade trade flows | supply_chain | EU/US chip dependency, Hsinchu chokepoint (90%) |
| `data/seed_data/tsmc_filing_excerpt.txt` | TSMC 20-F risk factors | filing | Cross-strait exposure, diversification |

**Loader API:**

```python
from ingestion.seed_loader import load_taiwan_scenario, seed_alert_context

count = load_taiwan_scenario()  # → int, documents ingested
alert_payload = seed_alert_context()  # → dict for alert evaluation
```

Metadata on every document: `source`, `date`, `category`, `scenario_name=taiwan_strait_escalation`.

**Aggregate metrics in seed:** `risk_level: HIGH`, `peak_tone: -9.1`, 5-day escalation timeline.

---

## Non-MCP Data

| Source | Access | Used by |
|--------|--------|---------|
| Ollama / Granite | `http://localhost:11434` | All agents, embeddings |
| ChromaDB | Local `data/chroma/` | Semantic memory |
| SQLite | Local `data/sqlite/` | Episodic memory |

---

## Known Limitations

- Geopolitical and Supply Chain agents use **simulated seed data**, not live GDELT or Comtrade feeds
- Yahoo Finance API is unofficial and may rate-limit or change without notice
- SEC EDGAR requires compliant User-Agent; bulk scraping beyond demo scale needs additional infrastructure
- All inference is **single-GPU serialized** through Ollama — concurrent agent calls queue

---

## Related Docs

- [PROTOCOLS.md](PROTOCOLS.md) — MCP JSON-RPC details
- [AGENTS.md](AGENTS.md) — agent responsibilities
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — Taiwan scenario walkthrough
