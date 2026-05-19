# Atlas Development Log

Step-by-step record of build progress and architecture decision records (ADRs).

---

## Phase 0 — Environment setup (2026-05-16)

**Goal:** Ollama + Granite running, LangGraph and BeeAI verified, project scaffolded.

### Environment

| Component | Version / detail |
|-----------|----------------|
| OS | Windows 11 |
| Python | 3.12.4 (venv at `.venv/`) |
| Ollama | 0.24.0 |
| LLM | `ibm/granite4.1:8b` (Q4_K_M, ~5.3 GB) |
| GPU constraint | RTX 3060 6GB — single model in VRAM at a time |

### Installed stack (via `pip install -e ".[dev]"`)

LangGraph, LangChain-Ollama, BeeAI Framework, A2A SDK, MCP, ChromaDB, SQLModel, Docling, APScheduler, Streamlit, Typer, httpx, feedparser, OpenTelemetry.

### Verification runs

```
$ python -m scripts.verify_ollama
Ollama base URL: http://localhost:11434
Expected model:  ibm/granite4.1:8b

Available models:
  - ibm/granite4.1:8b <-- configured

Sending test prompt to Granite...
Response: Atlas Phase 0 OK

PASS: Ollama + Granite are responding.
```

```
$ python -m examples.langgraph_hello
Model: ibm/granite4.1:8b
LangGraph -> Granite: Hello from LangGraph!
```

```
$ python -m examples.beeai_hello
Model: ollama:ibm/granite4.1:8b
BeeAI -> Granite: Hello from BeeAI!
```

### Scaffold added

PRD directory tree created with package `__init__.py` stubs: `agents/`, `protocols/`, `orchestration/`, `memory/`, `ingestion/`, `observability/`, `ui/`, `cli/`, `data/`, `tests/`, `docs/`.

### Phase 0 outcome

**Complete.** Ready for Phase 1 (first MCP server — Yahoo Finance).

---

## ADR-001: LangGraph orchestration + explicit BaseAgent specialist loop

**Status:** Accepted (Phase 0)

**Context:** Atlas needs multi-agent coordination with explicit state (DAGs, retries, HITL) and individual agents whose reasoning steps are easy to inspect and ground against MCP data. BeeAI was verified in Phase 0, but the production agent loop needed a clearer portfolio-readable shape.

**Decision:**

- **LangGraph** — orchestration layer: workflow graphs, shared state, conditional routing between agents.
- **Custom `BaseAgent` pattern** — specialist-agent construction with explicit `plan -> execute -> reflect` phases.
- **BeeAI** — evaluated and kept as a hello-world proof, but deferred for production agents.

**Consequences:**

- Synthesis/orchestration code lives under `orchestration/` (LangGraph).
- Specialist agents live under `agents/*` and inherit the custom `BaseAgent` loop.
- BeeAI remains installed because `examples/beeai_hello.py` proves the framework can call Granite, but Atlas agents do not depend on it.
- LangGraph, BaseAgent agents, and the BeeAI hello world all call the same Granite model via Ollama (`services/llm.py`).
- On 6GB VRAM, agents must serialize through Ollama; reflection loops need tight retry limits.

**Alternatives considered:** Pure BeeAI orchestration or BeeAI-native ReAct agents — deferred in favor of explicit DAG/state orchestration and explicit `plan -> execute -> reflect` specialists needed for demo traceability.

---

## Phase 2 — Market Intelligence Agent PoC

**Goal:** First working agent: natural-language query → MCP real data → Granite analysis → reflection → grounded answer.

### Added

| Path | Purpose |
|------|---------|
| `agents/base.py` | Abstract `plan` → `execute` → `reflect` loop with `max_retries=2` |
| `agents/market/agent.py` | Market Intelligence Agent (Granite + `McpClient`) |
| `agents/market/tools.py` | MCP `get_quote` helpers |
| `examples/market_agent_demo.py` | End-to-end demo (`TSMC` query) |

### Data grounding note

The Rust `mcp-market-data` quote response now keeps latest price/previous-close data on Yahoo's `1d` chart endpoint and fetches separate `1mo` chart history for volume baselines (`previous_day_volume`, `average_volume_5d`, `volume_vs_average_percent`). This gives Granite real data for volume comparisons instead of relying on prompt-only guardrails.

### Run (two terminals)

```bash
# Terminal 1 — Rust MCP server
cd rust && cargo run -p mcp-market-data

# Terminal 2 — Python agent (Ollama + Granite must be running)
python -m examples.market_agent_demo
```

### Phase 2 outcome

**Complete** when demo prints analysis + `sources` + `confidence` with live Yahoo quote data for the planned symbol.

---

## ADR-002: Reflection loop depth and retry policy

**Status:** Accepted (Phase 2)

**Context:** On 6GB VRAM, Granite runs one request at a time through Ollama. Each agent turn needs at least three LLM calls (plan, analyze, reflect). Unbounded retries would make demos slow and thrash VRAM.

**Decision:**

- **Three LLM calls per attempt:** `plan` (tool selection) → `execute` (analysis over MCP JSON) → `reflect` (grounding audit).
- **`max_retries = 2`** on `BaseAgent` → up to **3 full attempts** (initial + 2 retries).
- **Retry unit:** entire plan → execute → reflect loop, not reflect-only. Failed reflection feedback is passed into the next `plan` prompt so the model can fix symbol choice or tone.
- **Confidence:** set by the reflect step (`HIGH` / `MEDIUM` / `LOW`). If all attempts fail reflection, return the last draft with confidence forced to `LOW`.
- **Logging:** `print` step labels for now; replace with OpenTelemetry spans in Phase 10.

**Consequences:**

- Worst case ≈ 9 Granite calls per user query (3 attempts × 3 phases) — acceptable for PoC, not for production hot paths.
- Phase 7 Guardian Agent may add a second validation pass; keep Market Agent reflection lightweight to avoid duplicate work later.

**Alternatives considered:**

- Retry only `execute` — rejected; bad plans (wrong ticker) need replanning.
- `max_retries = 0` — rejected; reflection without retry cannot self-correct.
- BeeAI-native ReAct loop — deferred; explicit phases are easier to trace in demos and interviews.

---

## Phase 3 — A2A protocol layer

**Goal:** Agents can advertise capabilities with Agent Cards, be discovered over HTTP, and accept delegated tasks without callers importing their implementation.

### Added

| Path | Purpose |
|------|---------|
| `agents/market/agent_card.json` | Market Intelligence Agent A2A Agent Card |
| `agents/geopolitical/agent_card.json` | Stub Geopolitical Risk Agent Card |
| `agents/geopolitical/agent.py` | Placeholder agent returning a canned response |
| `protocols/a2a/server.py` | Raw HTTP JSON-RPC A2A server (`/.well-known/agent.json`, `/a2a`) |
| `protocols/a2a/client.py` | Async A2A discovery and `tasks/send` client |
| `protocols/a2a/discovery.py` | Local Agent Card registry and skill lookup |
| `examples/a2a_demo.py` | Starts Market A2A server, discovers it, delegates an AAPL task |

### Run (three services)

```bash
# Service 1 — Ollama must already be running with Granite pulled
ollama run ibm/granite4.1:8b

# Service 2 — Rust MCP market data server
cd rust && cargo run -p mcp-market-data

# Service 3 — A2A demo (starts Market Agent A2A server on port 9001)
python -m examples.a2a_demo
```

### Phase 3 outcome

**Complete** when the demo discovers the Market Agent's card, sends `tasks/send` over HTTP JSON-RPC, and receives an artifact containing the Market Agent's grounded Phase 2 result.

---

## ADR-003: A2A transport choice

**Status:** Accepted (Phase 3)

**Context:** Atlas needs agent-to-agent delegation before the Synthesis Agent exists. The transport should be easy to inspect in demos, work locally, and remain compatible with the A2A model of Agent Cards plus task delegation.

**Decision:**

- Use **HTTP + JSON-RPC 2.0** for Phase 3 A2A.
- Expose Agent Cards at `GET /.well-known/agent.json`.
- Expose task delegation at `POST /a2a` with methods `agent/card` and `tasks/send`.
- Return agent outputs as A2A-style artifacts with `parts` and structured `metadata`.

**Consequences:**

- Easy to debug with `curl`, browser fetches, and logs.
- Fits the current local portfolio demo scale without needing gRPC infrastructure.
- The Synthesis Agent can discover agents by skill and delegate over a stable HTTP boundary.
- We can add streaming, push notifications, or gRPC later if real-time multi-agent workloads require them.

**Alternatives considered:**

- **gRPC** — rejected for now: stronger typed contracts and streaming, but more setup and less demo-friendly inspection.
- **Direct Python imports** — rejected: couples agents to implementation details and defeats protocol-native design.

---

## Phase 4 — Multi-agent coordination with Synthesis Agent

**Goal:** One user query is planned as a small execution DAG, delegated to specialist agents over A2A, and synthesized into a unified briefing.

### Added

| Path | Purpose |
|------|---------|
| `agents/geopolitical/agent.py` | Model-knowledge geopolitical risk agent with limitation disclosure |
| `agents/supply_chain/agent.py` | Model-knowledge supply-chain agent with limitation disclosure |
| `agents/supply_chain/agent_card.json` | Supply Chain Agent A2A Agent Card |
| `agents/synthesis/planner.py` | Granite-generated execution plan over available Agent Cards |
| `agents/synthesis/agent.py` | Orchestrator that delegates over A2A and synthesizes results |
| `orchestration/state.py` | LangGraph state schema and reducers |
| `orchestration/graph.py` | Traceable `plan -> delegate_to_agents -> synthesize` StateGraph |
| `examples/synthesis_demo.py` | Taiwan Strait multi-agent demo |

### Run (four services)

```bash
# Service 1 — Ollama must already be running with Granite pulled
ollama run ibm/granite4.1:8b

# Service 2 — Rust MCP market data server
cd rust && cargo run -p mcp-market-data

# Service 3 — Synthesis demo (starts A2A servers on 9001, 9002, 9003)
python -m examples.synthesis_demo
```

### Phase 4 outcome

**Complete** when the demo starts three A2A specialist servers, creates a plan from their Agent Cards, delegates the Taiwan Strait query to Market, Geopolitical, and Supply Chain agents, then returns one synthesized briefing with per-agent sources and an execution plan.

---

## ADR-004: Plan object schema

**Status:** Accepted (Phase 4)

**Context:** The Synthesis Agent needs an explicit, inspectable plan so the demo can show why specialists were selected and how work moved across A2A boundaries. The plan should be simple enough for Granite to generate reliably and structured enough for LangGraph and future observability.

**Decision:**

Use a small DAG-shaped JSON object:

```json
{
  "steps": [
    {
      "agent": "market",
      "task": "Assess market impact and relevant semiconductor equities",
      "depends_on": []
    }
  ],
  "rationale": "Why these agents were selected"
}
```

Rules:

- `agent` uses stable keys derived from Agent Cards (`market`, `geopolitical`, `supply_chain`).
- `task` is the delegated natural-language instruction sent over A2A `tasks/send`.
- `depends_on` is present even though Phase 4 runs sequentially; it keeps the future DAG shape explicit.
- Execution remains sequential for now because local Granite/Ollama is the single GPU bottleneck.

**Consequences:**

- Easy to print, inspect, and trace in demos.
- Works naturally with LangGraph nodes and future OpenTelemetry spans.
- Leaves room for Phase 5+ parallelism or conditional routing without changing the public plan shape.

**Alternatives considered:**

- Free-form plan text — rejected; hard to execute or trace.
- Full graph schema with typed edges and conditions — deferred; too much machinery for Phase 4.
- Directly asking Granite to call agents without a plan object — rejected; weaker explainability and harder debugging.

---

## Phase 5 — Three-tier memory architecture

**Goal:** Add persistent memory so agents can retrieve semantic context, persist run history, and expose per-query working memory.

### Added

| Path | Purpose |
|------|---------|
| `services/embeddings.py` | Ollama `/api/embed` wrapper using `OLLAMA_EMBED_MODEL` with chat-model fallback |
| `memory/semantic.py` | ChromaDB semantic memory (`SemanticMemory`) |
| `memory/episodic.py` | SQLite + SQLModel episodic memory (`EpisodicMemory`) |
| `memory/working.py` | Per-query scratchpad (`WorkingMemory`) |
| `examples/memory_demo.py` | Standalone proof that all three memory tiers work |

### Modified

| Path | Change |
|------|--------|
| `agents/market/agent.py` | Queries semantic memory before analysis; logs successful executions to episodic memory |
| `agents/synthesis/agent.py` | Queries similar past briefings; logs final briefings to episodic memory |
| `examples/synthesis_demo.py` | Saves JSON run logs and SQLite episodic records; prints memory persistence summary |
| `observability/run_logger.py` | Adds `memory_stats` to JSON run artifacts |
| `.env.example` | Adds `OLLAMA_EMBED_MODEL=granite-embedding:278m` |
| `pyproject.toml` | Adds `memory`, `observability`, and `atlas-memory-demo` |

### Run

```bash
# Pull recommended embedding model once
ollama pull granite-embedding:278m

# Prove all three memory tiers
python -m examples.memory_demo
```

### Phase 5 outcome

**Complete** when semantic memory can ingest/query a sample document, episodic memory can store/query a briefing, and working memory can accumulate/format/clear per-query state.

---

## ADR-005: Episodic memory schema design

**Status:** Accepted (Phase 5)

**Context:** Atlas needs durable memory of user-facing briefings, agent executions, and future alerts. This memory should support auditability, trend analysis, and demo reproducibility without introducing operational database overhead.

**Decision:**

- Use **SQLite + SQLModel** for episodic memory.
- Store three append-only tables:
  - `BriefingRecord` — final synthesized outputs, plans, sources, confidence, duration.
  - `AgentExecution` — per-agent task/result/confidence/duration records.
  - `AlertRecord` — future alert trigger and assessment history.
- Store plan, sources, agent chains, and result payloads as JSON columns.
- Keep records append-only for now; corrections should create new records instead of mutating history.

**Why these tables:**

- `BriefingRecord` is the user-facing historical memory.
- `AgentExecution` lets us inspect which specialist produced which result.
- `AlertRecord` reserves the same pattern for Phase 9 alerting.

**Why append-only:**

- Preserves the decision trail for interview demos and future observability.
- Makes confidence history meaningful over time.
- Avoids silent rewriting of previous assessments.

**Why SQLite over Postgres:**

- Atlas is a single-user, local-first demo target.
- SQLite has no service dependency and works offline.
- SQLModel keeps a future path to Postgres if the project becomes multi-user.

**Consequences:**

- Queries are simple and local.
- JSON fields are flexible while schemas are still emerging.
- More advanced search/ranking can be added later without changing the persisted event model.

---

## Phase 6 — Research & Filing Agent with SEC EDGAR MCP server

**Goal:** Add the fourth specialist agent backed by a real Rust MCP server for SEC EDGAR filings.

### Added

| Path | Purpose |
|------|---------|
| `rust/mcp-edgar/Cargo.toml` | Rust crate config for the SEC EDGAR MCP server |
| `rust/mcp-edgar/src/main.rs` | Axum server on `:8002` with `/health` and `/mcp` endpoints |
| `rust/mcp-edgar/src/mcp.rs` | MCP JSON-RPC router exposing `company_filings`, `filing_text`, and `full_text_search` |
| `rust/mcp-edgar/src/edgar.rs` | SEC EDGAR client with User-Agent, CIK padding, rate-limit delay, submissions parsing |
| `agents/research/agent.py` | Research & Filing Agent using EDGAR MCP plus semantic memory ingestion |
| `agents/research/tools.py` | Python MCP helpers for EDGAR tools |
| `agents/research/agent_card.json` | Research Agent A2A Agent Card on `:9004` |
| `examples/edgar_demo.py` | Standalone EDGAR MCP + Research Agent demo |

### Modified

| Path | Change |
|------|--------|
| `rust/Cargo.toml` | Added `mcp-edgar` workspace member |
| `agents/research/__init__.py` | Exports `ResearchFilingAgent` |
| `agents/synthesis/planner.py` | Planner now selects Research Agent for filings, earnings, SEC data, risk factors, and company financial detail |
| `examples/synthesis_demo.py` | Starts Research A2A server on `:9004` and requires EDGAR MCP on `:8002` |
| `pyproject.toml` | Adds `atlas-edgar-demo` console script |

### SEC EDGAR implementation notes

- Every SEC HTTP request uses `User-Agent: Atlas-MCP/0.1 (atlas-project@example.com)`.
- `edgar::pad_cik(cik: &str) -> String` normalizes CIKs to EDGAR's 10-digit submissions format.
- `edgar::sec_delay() -> ()` waits 125 ms before upstream calls, keeping local demos below the SEC 10 requests/second guidance.
- `company_filings` resolves tickers through `company_tickers.json`, fetches `data.sec.gov/submissions/CIK##########.json`, and returns recent filing metadata with primary document URLs.
- `filing_text` resolves the primary document for an accession number, fetches it from SEC Archives, strips HTML tags, and returns the first 10,000 characters.
- `full_text_search` calls SEC's `efts.sec.gov/LATEST/search-index` endpoint.

### Run

```bash
# Service 1 — Ollama must already be running with Granite pulled
ollama run ibm/granite4.1:8b

# Service 2 — Market MCP for the Market Agent
cd rust && cargo run -p mcp-market-data

# Service 3 — EDGAR MCP for the Research Agent
cd rust && cargo run -p mcp-edgar

# Standalone EDGAR demo
python -m examples.edgar_demo

# Full four-agent synthesis demo
python -m examples.synthesis_demo
```

### Verification

- `cargo check -p mcp-edgar` completed successfully.
- `python -m ruff check agents\research examples\edgar_demo.py examples\synthesis_demo.py agents\synthesis\planner.py` completed successfully.
- `examples/edgar_demo.py` completed successfully: listed EDGAR tools, fetched AAPL filings, fetched filing text, ingested filing text into semantic memory, and passed Research Agent reflection.
- `examples/synthesis_demo.py` completed successfully with four A2A agents, included Research in the plan, and saved `runs\20260517_200249.json`.

### Phase 6 outcome

**Complete.** Atlas now has four specialist agents: Market, Geopolitical, Supply Chain, and Research/Filing. The Research Agent is grounded by a Rust EDGAR MCP server rather than model knowledge alone.

---

## Phase 7 — Guardian Agent

**Goal:** Add a second-pass quality gate that validates synthesized briefings before they reach the user.

### Added

| Path | Purpose |
|------|---------|
| `agents/guardian/agent.py` | `GuardianAgent` validator with `GuardianVerdict` and `ClaimCheck` TypedDicts |
| `agents/guardian/agent_card.json` | Guardian Agent Card on `:9005` with `validate` and `confidence_score` skills |
| `examples/guardian_demo.py` | Standalone demo with one grounded claim and one fabricated claim |

### Modified

| Path | Change |
|------|--------|
| `agents/guardian/__init__.py` | Exports `GuardianAgent`, `GuardianVerdict`, and `ClaimCheck` |
| `orchestration/graph.py` | Adds `guardian` node after synthesis and one retry path for `LOW` confidence |
| `orchestration/state.py` | Adds `guardian_verdict` and `guardian_retries` state fields |
| `agents/synthesis/agent.py` | Accepts Guardian feedback during retry and keeps synthesis grounded to specialist sources |
| `agents/synthesis/planner.py` | Prevents Guardian Agent Card from being selected as a specialist delegate |
| `examples/synthesis_demo.py` | Prints Guardian validation output and saves verdict in run data |
| `observability/run_logger.py` | Persists `guardian_verdict` in run JSON |
| `memory/episodic.py` | Stores Guardian verdict inside the existing `agent_results` JSON payload |
| `pyproject.toml` | Adds `atlas-guardian-demo` console script |

### Verification

- `python -m ruff check agents\guardian agents\synthesis orchestration examples\guardian_demo.py examples\synthesis_demo.py memory\episodic.py observability\run_logger.py` completed successfully.
- `examples/guardian_demo.py` completed successfully and flagged the fabricated export-ban claim as unsupported.
- `examples/synthesis_demo.py` completed successfully with Guardian validation and saved `runs\20260517_204248.json` including `guardian_verdict`.

### Phase 7 outcome

**Complete** when the full synthesis flow routes `plan -> delegate_to_agents -> synthesize -> guardian -> END`, attaches a Guardian verdict to the final briefing, and retries synthesis once if Guardian confidence is `LOW`.

---

## ADR-007: Confidence threshold calibration and Guardian separation of concerns

**Status:** Accepted (Phase 7)

**Context:** Atlas now combines live MCP data, model-knowledge specialist outputs, SEC filing evidence, memory context, and synthesized prose. The final user-facing answer needs a second-pass validation layer that can flag unsupported claims without becoming another content generator.

**Decision:**

- Add `GuardianAgent` as a validation-only agent. It does not extend `BaseAgent` and does not use `plan -> execute -> reflect`.
- `GuardianAgent.validate(query, briefing, agent_results, sources)` makes one Granite call and returns structured `GuardianVerdict`.
- Confidence calibration:
  - `HIGH`: directly supported by multiple fresh sources or a clearly cited authoritative source.
  - `MEDIUM`: supported by one source, stale-but-relevant context, or reasonable synthesis across agents.
  - `LOW`: unsupported, contradicted, stale for time-sensitive claims, or speculative language stated as fact.
- Guardian does not fix or rewrite content. It flags issues and assigns confidence; synthesis retry logic decides what to do.
- LangGraph retries synthesis once when Guardian returns `LOW`, then returns the flagged result if confidence remains `LOW`.

**Consequences:**

- Validation remains separate from content generation, keeping responsibilities clear.
- Guardian flags can be persisted and audited in run logs and episodic memory.
- A single retry avoids infinite loops and controls local Granite runtime cost.
- Future phases can route Guardian failures to human review or targeted specialist re-query without changing the verdict schema.

---

## Phase 8 — Scheduled briefings

**Goal:** Generate Atlas intelligence briefings automatically from a watchlist or cron schedule.

### Added

| Path | Purpose |
|------|---------|
| `services/briefing.py` | `BriefingEngine` that runs one full synthesis + Guardian pipeline per topic |
| `services/briefing_templates.py` | Pure formatting helpers for daily briefings and summary lines |
| `services/scheduler.py` | `AtlasScheduler` wrapper around APScheduler's `AsyncIOScheduler` |
| `examples/briefing_demo.py` | Immediate scheduled-style briefing demo using the default watchlist |
| `examples/scheduler_demo.py` | Autonomous scheduler demo using a 60-second cron cadence for 3 minutes |

### Modified

| Path | Change |
|------|--------|
| `memory/episodic.py` | Adds `briefing_type`, `topics`, `delta_from_last`, SQLite migration helper, and `get_last_briefing(topic)` |
| `observability/run_logger.py` | Adds scheduled-briefing fields to run JSON payloads |
| `pyproject.toml` | Adds `atlas-briefing-demo` and `atlas-scheduler-demo` scripts |

### Implementation notes

- `BriefingEngine.generate_briefing()` defaults to `["semiconductor supply chain", "US-China trade tensions", "major market movements", "SEC filing activity"]`.
- Each topic becomes a synthesis graph invocation, so it goes through planner, A2A specialists, synthesis, Guardian validation, run logging, and episodic memory.
- `BriefingEngine` computes deterministic deltas from `EpisodicMemory.get_last_briefing(topic)` before running the next topic.
- `AtlasScheduler` uses `AsyncIOScheduler` because Atlas agent pipelines are async.
- The scheduler prints `format_summary_line()` after each generated briefing.
- Formatting functions are pure: no LLM calls, no data fetching, no memory writes.

### Verification

- `python -m ruff check services\briefing.py services\briefing_templates.py services\scheduler.py examples\briefing_demo.py examples\scheduler_demo.py memory\episodic.py observability\run_logger.py` completed successfully.
- Briefing template smoke test completed successfully.
- Import and memory smoke test completed successfully, including `EpisodicMemory.get_last_briefing("semiconductor supply chain")`.

### Phase 8 outcome

**Complete** when `examples/briefing_demo.py` can generate a full watchlist briefing and `examples/scheduler_demo.py` can schedule autonomous recurring briefings.
