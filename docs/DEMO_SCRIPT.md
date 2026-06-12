# Taiwan Strait Demo — Interview Script

Step-by-step walkthrough for live demos and portfolio interviews. Expected output shapes: [data/sample_scenarios/taiwan_demo_expected_output.md](../data/sample_scenarios/taiwan_demo_expected_output.md).

Pre-flight checklist: [VERIFICATION.md](VERIFICATION.md)

---

## Prerequisites (5 min setup)

Open three terminals before the interview:

| Terminal | Command |
|----------|---------|
| A | `ollama serve` (if not already running) |
| B | `cd rust && cargo run -p mcp-market-data` |
| C | `cd rust && cargo run -p mcp-edgar` |

From project root with venv activated:

```powershell
pip install -e ".[dev]"
ollama pull ibm/granite4.1:8b
ollama pull granite-embedding:278m
atlas status
```

**Talking point:** Atlas is local-first — Granite on Ollama, Rust MCP servers for data, Python agents for reasoning. No cloud API keys.

---

## Option A — One-command demo (recommended)

```powershell
atlas-taiwan-demo
```

Runs all six steps below automatically (~5–12 min depending on GPU). Narrate each `[Step N]` banner as it appears.

---

## Option B — Step-by-step (for deeper Q&A)

### Step 1 — Seed data ingestion

**What to say:** We simulate GDELT geopolitical events, a TSMC filing excerpt, and UN Comtrade-style trade flows. Seed data lands in ChromaDB semantic memory so Geopolitical and Supply Chain agents have grounded context without a live GDELT MCP.

**Command (if not using full demo):**

```powershell
python -c "from ingestion.seed_loader import load_taiwan_scenario; print(load_taiwan_scenario())"
```

**Look for:** `Ingested 12 documents into semantic memory` (or similar chunk count).

---

### Step 2 — Real-time alert

**What to say:** The alert engine evaluates fresh seed-shaped data against a Granite JSON condition. When aggregate `risk_level == HIGH`, a deterministic fallback ensures the demo always fires — useful when the LLM evaluator is conservative.

**Look for:**

```
ALERT [HIGH] Taiwan Strait tension spike
Summary: Taiwan Strait GDELT aggregate risk_level is HIGH with peak_tone -9.1 over five days.
```

Alert is logged to episodic SQLite and `runs/`.

---

### Step 3 — Full multi-agent synthesis

**Query:**

```text
What's the exposure risk if Taiwan Strait tensions escalate? Consider semiconductor supply chains, market impact, and TSMC filing risk factors.
```

**What to say:** LangGraph orchestrates plan → delegate → synthesize → Guardian. Four A2A specialists run in parallel where the DAG allows:

| Agent | Port | Data |
|-------|------|------|
| Market | `:9001` | Live TSM quote via MCP `:8001` |
| Geopolitical | `:9002` | Seed GDELT from semantic memory |
| Supply Chain | `:9003` | Seed trade flow / chokepoints |
| Research | `:9004` | SEC EDGAR via MCP `:8002` |

Guardian validates grounding **after** synthesis — it does not rewrite the briefing.

**Look for:** `Overall confidence: MEDIUM` or `HIGH`, `trace_id: <hex>`, multi-paragraph combined analysis covering chips, market, and filings.

**Artifacts:** `runs/YYYYMMDD_HHMMSS.json`, SQLite briefing record, `data/traces/` span file.

---

### Step 4 — Scheduled briefing

**What to say:** Same pipeline as ad-hoc queries, but driven by `BriefingEngine` with watchlist topics and delta-from-last tracking in episodic memory.

**Look for:** `Briefing [custom] topics=1 risk=...` and a delta line (first run: baseline created).

---

### Step 5 — OpenTelemetry trace

**What to say:** Every LLM call, MCP fetch, and A2A delegation is a span. `trace_id` links run JSON to the trace file.

**Look for:** Indented span tree with `synthesis.run`, `a2a.send_task`, `mcp.tools/call`, `guardian.validate`.

**Also show:**

```powershell
atlas traces list
atlas traces show <trace_id>
```

Or open **Trace Viewer** in the dashboard.

---

### Step 6 — Summary box

**What to say:** Recap the architecture story — Rust data layer, Python intelligence layer, protocol-native MCP + A2A, three-tier memory, Guardian quality gate.

The demo prints a boxed summary listing protocols, agents, memory tiers, and timing.

---

## Alternate entry points (same pipeline)

After seeding once:

```powershell
atlas query "What's the exposure risk if Taiwan Strait tensions escalate? Consider semiconductor supply chains, market impact, and TSMC filing risk factors."
```

**Dashboard:**

```powershell
atlas-dashboard
```

Query page → paste the same question. Tabs: Analysis | Guardian | Sources | Trace.

---

## Fallbacks

| Situation | Fallback |
|-----------|----------|
| MCP servers not running | Run `atlas status`; start `:8001` and `:8002` before query/briefing steps |
| Ollama slow or CPU-only | Warn audience synthesis may take 5–10 min; show trace/run artifacts from a prior run |
| Guardian returns LOW confidence | Point to Guardian tab — claim checks show which assertions failed grounding; LangGraph may retry synthesize once |
| Alert LLM does not trigger | Demo uses deterministic HIGH fallback when seed aggregate `risk_level == HIGH` |
| Yahoo or SEC API errors | Market/Research agents surface MCP errors in agent results; other agents still contribute from seed memory |
| EDGAR rate limits | Research agent may return fewer filing details; filing excerpt still in semantic memory from seed |

---

## Q&A prompts (optional)

- **Why Rust for MCP?** Data fetching, validation, rate limits, and security middleware close to the wire; Python owns agent reasoning.
- **Why Guardian separate from synthesis?** Separation of concerns — specialists analyze, synthesis merges, Guardian audits without rewriting (ADR-007).
- **What's simulated vs live?** Market quotes and SEC filings are live; GDELT and Comtrade use seed data in ChromaDB until dedicated MCP servers exist.
- **Security?** Phase 15 defaults bind to `127.0.0.1`; optional bearer auth and rate limits — see [SECURITY.md](SECURITY.md).

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [VERIFICATION.md](VERIFICATION.md) | Pre-interview command checklist |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design (~5 min read) |
| [AGENTS.md](AGENTS.md) | Per-agent responsibilities |
| [SECURITY.md](SECURITY.md) | Production hardening |
