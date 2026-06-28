# Atlas — Global Intelligence Platform | Project Context

**Atlas** is a global business intelligence system powered by autonomous AI agents that communicate via industry-standard protocols. This document is the current plan and master reference point. Nothing here is sacred except the core goal.

**Status (May 2026):** Phases **0–15 are complete**. All core pipelines are implemented and demo-verified. See [README.md](README.md) for quick start and [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for the Taiwan Strait interview walkthrough.

---

## Core Goal

Build a system where specialized AI agents continuously gather, analyze, and synthesize global business intelligence — financial markets, geopolitical signals, trade and supply chain data, public filings, and news — into a unified knowledge base that a user can query in plain English, receive scheduled briefings from, and get real-time alerts when conditions change.

This is a **portfolio project** designed with:

- Agentic AI architecture using emerging industry standards (MCP, A2A)
- Multi-agent orchestration with explicit state management (LangGraph)
- RAG pipelines with three-tier memory architecture
- Reflection and self-correction patterns
- Full observability and decision traceability
- Production-grade engineering on a fully open-source, on-prem stack
- **Polyglot systems design** — Rust for the performance-critical data layer (MCP servers, ingestion), Python for the intelligence layer (agents, orchestration, UI)

---

## Hard Constraints

These don't change without explicit discussion:

- **100% open source.** Zero proprietary dependencies. Every component must be Apache 2.0, MIT, or equivalent. No OpenAI, no Claude API, no paid services.
- **On-prem / air-gapped capable.** The system must run entirely on local hardware with no external API calls required at runtime. Data ingestion can pull from the internet, but inference and analysis must be self-contained.
- **Single-user demo target.** Auth and multi-tenancy are out of scope. The system is optimized for one analyst operating it locally.
- **Protocol-native.** All data source connections use MCP. All inter-agent communication uses A2A. No ad-hoc integration patterns.

---

## Architecture Overview

Atlas is a **hybrid Rust + Python system**. The performance-critical data layer (MCP servers, data ingestion, embedding pipeline) is built in Rust. The intelligence layer (agents, orchestration, LLM interaction, UI) is built in Python. The two layers communicate over HTTP — Rust services expose MCP endpoints that the Python agent layer calls as an MCP client.

This split reflects production practice: the hot path is Rust, the reasoning layer is Python. It also demonstrates architectural maturity — knowing where language choice matters and where it doesn't.

**MCP (Model Context Protocol)** — Anthropic's open standard for connecting agents to tools and data sources. Every external data adapter in Atlas (FRED, EDGAR, GDELT, Yahoo Finance, etc.) is implemented as a **Rust MCP server**. This means any MCP-compatible client can plug into Atlas's data layer. We're building infrastructure, not a closed system. MCP is governed by the Linux Foundation's Agentic AI Foundation (AAIF) and is adopted by every major AI provider. Atlas implements MCP servers in Rust directly against the spec using `axum`, `serde`, and `tokio` — building from the spec demonstrates deeper protocol understanding than wrapping an SDK.

**A2A (Agent-to-Agent Protocol)** — Google's open standard for inter-agent communication. Atlas agents discover each other's capabilities through Agent Cards, delegate tasks via the protocol, and exchange structured results over HTTP with JSON-RPC 2.0. A2A reached v1.0 in early 2026 with support for gRPC and signed Agent Cards. This means a third-party agent could theoretically be plugged into the Atlas system and participate without modification.

**LangGraph** — The orchestration layer (Python). Agent workflows are modeled as directed graphs with explicit state, conditional routing, retry logic, and human-in-the-loop checkpoints. The Synthesis Agent's execution plan is itself a DAG — fully traceable in OpenTelemetry.

**BeeAI** — Evaluated in Phase 0 with a Granite hello-world demo, but not used for production Atlas agents. Specialist agents use the custom `BaseAgent` pattern with explicit `plan -> execute -> reflect` phases because that flow is easier to inspect, test, and ground against MCP data.

```
                    ┌─────────────────┐
                    │      User       │
                    │  (CLI / Web UI) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   LangGraph     │
                    │  Orchestrator   │  ← Python
                    │  (DAG planner)  │
                    └────────┬────────┘
                             │ A2A Protocol
          ┌──────────────────┼──────────────────┐
          │                  │                  │
  ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │   Market     │  │  Geopolitical│  │ Supply Chain │
  │   Intel      │  │  Risk        │  │ & Trade      │  ← Python
  │   Agent      │  │  Agent       │  │ Agent        │
  └───────┬──────┘  └───────┬──────┘  └───────┬──────┘
          │                  │                  │
          │    MCP Protocol  │   MCP Protocol   │
          │                  │                  │
  ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │ FRED, Yahoo  │  │ GDELT, RSS   │  │ Comtrade,    │
  │ Finance,     │  │ UN/WTO,      │  │ BIS, USITC,  │
  │ Alpha Vant.  │  │ Gov releases │  │ Port data    │  ← Rust
  │ (MCP servers)│  │ (MCP servers)│  │ (MCP servers) │
  └──────────────┘  └──────────────┘  └──────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Three-Tier     │
                    │  Memory System  │
                    │                 │
                    │  Semantic:      │
                    │   ChromaDB      │
                    │  Episodic:      │
                    │   SQLite        │
                    │  Working:       │
                    │   In-context    │
                    └─────────────────┘
```

**As built:** Live MCP servers are `mcp-market-data` (Yahoo) and `mcp-edgar` (SEC). Geopolitical and trade data for the Taiwan demo come from seed files ingested into semantic memory; additional Rust MCP crates remain planned.

## Language Boundary

The Rust/Python split follows a clear rule: **Rust owns data, Python owns reasoning.**

| Layer | Language | Why |
|-------|----------|-----|
| MCP servers (all data adapters) | Rust | I/O-bound, concurrent network requests, parsing, low memory footprint (5-20MB per server vs 100-200MB Python) |
| Data ingestion | Python (`ingestion/seed_loader.py`) | Demo seed → semantic memory; full live pipeline planned |
| Embedding service | Python (`services/embeddings.py`) | Ollama `/api/embed` for ChromaDB vectors |
| Agent logic + reflection | Python | Rapid iteration, string manipulation, LLM interaction |
| LangGraph orchestration | Python | Framework is Python-only, state management |
| A2A protocol layer | Python | SDK is Python-only |
| Memory interfaces | Python | ChromaDB and SQLModel are Python-native |
| CLI + Web UI | Python + TypeScript | Typer CLI; Carbon React UI + FastAPI API |

The boundary is HTTP. Rust MCP servers expose standard MCP endpoints. Python agents connect as MCP clients. Neither side knows or cares what language the other is written in — that's the point of protocol-native design.

---

## Agent Architecture

Each agent is an autonomous unit with a defined responsibility, its own MCP tool connections, a self-reflection loop, and an A2A Agent Card describing its capabilities to the system. Every agent follows a common execution pattern:

```
Input → Plan → Execute → Self-Reflect → Output (or retry)
```

No agent passes output downstream without first critiquing its own work. The Guardian Agent provides a second-pass validation, but it is not the only quality gate — reflection is baked into every agent.

### Core Agents

**Market Intelligence Agent**

- Domain: Financial markets — equities, commodities, forex, macro indicators
- **As built MCP:** Yahoo Finance via `mcp-market-data` (:8001)
- **Planned MCP:** FRED, Alpha Vantage (free tier)
- Capabilities: Anomaly detection, trend shift identification, cross-asset correlation, technical indicator calculation
- Reflection: Validates that claims are grounded in data, checks for stale data, confirms statistical significance before surfacing signals
- A2A Agent Card: Advertises capabilities like `market_snapshot`, `anomaly_scan`, `correlation_check`

**Geopolitical Risk Agent**

- Domain: Conflicts, sanctions, elections, policy shifts, trade agreements
- **As built:** Semantic memory seed data (GDELT-style Taiwan scenario) + Granite model knowledge with explicit limitation disclosure
- **Planned MCP servers:** GDELT, ACLED, RSS feeds (Reuters, AP, government releases), UN/WTO
- Capabilities: Event detection, entity extraction (NER), regional risk scoring, temporal trend analysis
- Reflection: Cross-references multiple sources before assigning risk scores, flags single-source assessments, checks recency
- A2A Agent Card: Advertises `risk_assessment`, `event_timeline`, `entity_exposure`

**Supply Chain & Trade Agent**

- Domain: Global trade flows, tariffs, shipping disruptions, commodity dependencies
- **As built:** Semantic memory seed data (simulated UN Comtrade trade flows) + Granite model knowledge with explicit limitation disclosure
- **Planned MCP servers:** UN Comtrade, WTO datasets, BIS, USITC, port/shipping open data
- Capabilities: Dependency graph construction, tariff impact modeling, disruption detection, chokepoint identification
- Reflection: Validates trade flow data against multiple sources, checks for data lag, confirms causal chains before asserting disruption impact
- A2A Agent Card: Advertises `dependency_map`, `disruption_alert`, `tariff_impact`

**Research & Filing Agent**

- Domain: SEC filings, earnings reports, annual reports, regulatory filings
- **As built MCP:** SEC EDGAR via `mcp-edgar` (:8002) — `company_filings`, `filing_text`, `full_text_search`
- **Planned MCP:** Open Corporates, government data portals
- Capabilities: Key financial extraction, sentiment analysis on forward-looking statements, filing diff detection (what changed from last quarter)
- Reflection: Verifies extracted numbers against source documents, flags ambiguous language, checks for selective quoting
- A2A Agent Card: Advertises `filing_summary`, `financial_extract`, `filing_diff`

**Synthesis Agent (Orchestrator)**

- Role: Receives user queries and generates an explicit execution plan — a DAG of tasks delegated to specialist agents via A2A
- Plan object: Every query produces a traceable plan: which agents to call, in what order, what information to gather, what conflicts to resolve
- Capabilities: Cross-domain reasoning, conflict resolution, signal correlation, briefing generation, alert dispatch
- Reflection: After plan execution, evaluates whether the plan produced a sufficient answer. If not, generates a revised plan and re-executes (up to a configurable retry limit)
- Does NOT have its own MCP data connections — it reasons over agent outputs, not raw data
- A2A Agent Card: Advertises `query`, `briefing`, `alert_config`

**Guardian Agent**

- Role: Second-pass validator on all outputs before they reach the user
- Capabilities: Hallucination detection (does the claim trace to a source?), data staleness check, source reliability scoring, confidence calibration
- Flags confidence levels on every assertion: HIGH (multiple corroborating sources), MEDIUM (single reliable source), LOW (inferred or extrapolated)
- Does NOT generate content — only validates and annotates
- A2A Agent Card: Advertises `validate`, `confidence_score`

---

## Three-Tier Memory Architecture

Agents don't just retrieve and forget. Atlas maintains three distinct memory layers:

**Semantic Memory (ChromaDB)** Long-term knowledge store. Documents, filings, and seed scenario data are chunked, embedded (`granite-embedding:278m` via Ollama), and stored as vectors. Agents query semantic memory during execution for relevant context.

**Episodic Memory (SQLite)** Historical record of system events. Every briefing generated, every alert fired, every agent execution and its outcome, every plan the Synthesis Agent created. This enables temporal reasoning: "What did I assess about semiconductor risk last month?" or "How has the geopolitical risk score for Taiwan changed over the past 90 days?" Episodic memory is append-only and immutable — an audit trail.

**Working Memory (In-Context)** Per-query scratchpad. When the Synthesis Agent generates a plan and delegates to specialist agents, the intermediate results, reasoning chains, and conflict notes live in working memory for the duration of that query. Discarded after the response is delivered (but the final output and plan are logged to episodic memory).

---

## Interaction Modes

### 1. Natural Language Q&A

User asks a question → Synthesis Agent generates a plan (DAG) → delegates to specialist agents via A2A → agents retrieve from MCP data sources, reason, self-reflect → Synthesis Agent collects results, resolves conflicts, self-reflects on plan quality → Guardian Agent validates → grounded answer with citations and confidence levels returned to user.

Example: *"What's the exposure risk if China restricts rare earth exports to the EU in the next 6 months?"*

Plan generated:

1. Geopolitical Risk Agent → assess likelihood of export restriction based on recent signals
2. Supply Chain Agent → map EU rare earth dependencies, identify affected industries
3. Market Intelligence Agent → pull commodity pricing trends, identify companies with exposure
4. Synthesis Agent → correlate findings, generate risk assessment with confidence levels

### 2. Scheduled Briefings

Automated daily/weekly intelligence reports generated on a cron schedule. Agents proactively scan their domains, surface what's changed since the last briefing, and the Synthesis Agent compiles a structured report. Briefings are stored in episodic memory for trend analysis.

Output format: Structured briefing with sections ranked by risk/relevance, source citations, confidence flags, and a "what changed since last briefing" delta.

### 3. Real-Time Monitoring & Alerts

Agents run continuous watch loops against their MCP data sources. When a threshold is crossed or a significant event is detected, an alert fires through the Synthesis Agent with an impact assessment.

Example flow: `AlertEngine` evaluates fresh MCP data (or demo seed context) against Granite JSON conditions → triggered alert logged to episodic memory → delivered via CLI and dashboard.

---

## Demo Scenario (The Story)

The end-to-end demo walks through a single compelling scenario that exercises every agent, both protocols, all three memory tiers, and the full observability stack.

**Run:** `atlas-taiwan-demo` (or `atlas query` / dashboard Query page with the same question after seeding). Walkthrough: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

**Trigger:** Taiwan Strait tensions spike (simulated via seed data in `data/seed_data/` → ChromaDB semantic memory)

1. **Seed loader** ingests GDELT-style events, trade-flow data, and TSMC filing excerpt into semantic memory
2. **Alert fires** — `taiwan_strait_tension` rule evaluates seed aggregate metrics (HIGH severity)
3. **Geopolitical Risk Agent** queries semantic memory for GDELT-style seed context → self-reflects → publishes via A2A
4. **Supply Chain Agent** queries semantic memory for trade-flow / chokepoint seed data → publishes via A2A
5. **Market Intelligence Agent** pulls live TSM quote from Yahoo Finance via `mcp-market-data` MCP → publishes via A2A
6. **Research Agent** pulls TSMC filings from EDGAR via `mcp-edgar` MCP → publishes via A2A
7. **Synthesis Agent** collects outputs → generates unified briefing → Guardian validates with confidence levels
8. **Scheduled briefing** runs for topic "Taiwan Strait semiconductor risk" with episodic delta
9. **OpenTelemetry trace** links run log, CLI output, and dashboard Trace Viewer via `trace_id`

An interviewer watching this demo sees: protocol-native architecture (MCP + A2A), multi-agent coordination with explicit planning, reflection at every stage, three-tier memory in action, full observability, polyglot Rust/Python design, and a real-world scenario that matters.

---

## Data Sources (Open & Free)

Live data adapters are **Rust MCP servers**. Geopolitical and trade data for the Taiwan demo use **seed files** ingested into semantic memory until dedicated MCP servers are built.

### Implemented

| Category | MCP Server (Rust) | Port | Sources |
|----------|-------------------|------|---------|
| Financial markets | `mcp-market-data` | 8001 | Yahoo Finance (`get_quote`) |
| Corporate filings | `mcp-edgar` | 8002 | SEC EDGAR submissions, filing text, full-text search |

### Demo seed data (semantic memory)

| File | Simulates | Used by |
|------|-----------|---------|
| `data/seed_data/taiwan_scenario.json` | GDELT-style conflict events | Geopolitical Agent, alerts |
| `data/seed_data/trade_flow_data.json` | UN Comtrade trade flows | Supply Chain Agent |
| `data/seed_data/tsmc_filing_excerpt.txt` | TSMC 20-F risk factors | Research Agent (supplement) |

Loaded via `ingestion/seed_loader.py` → `load_taiwan_scenario()`.

### Planned (not yet built)

| Category | MCP Server | Sources |
|----------|------------|---------|
| Geopolitical events | `mcp-geopolitical` | GDELT, ACLED, RSS feeds |
| Government / policy | `mcp-gov` | UN, WTO, government press releases |
| Trade & supply chain | `mcp-trade` | UN Comtrade, WTO, BIS, USITC |
| Macro indicators | `mcp-macro` | World Bank, IMF, OECD, BLS |

All sources must be publicly accessible with no API key required, or free-tier API keys only.

---

## Tech Stack

| Layer | Tool | Language | Role |
|-------|------|----------|------|
| MCP servers | reqwest, serde, tokio, axum | Rust | Data source adapters — HTTP fetching, JSON parsing, MCP protocol |
| Data ingestion | `ingestion/seed_loader.py` | Python | Taiwan demo seed → ChromaDB |
| Embedding service | `services/embeddings.py` | Python | Ollama `/api/embed` for semantic memory |
| Agent orchestration | LangGraph | Python | DAG-based workflow coordination, state management, conditional routing, retry logic |
| Agent construction | Custom `BaseAgent` pattern | Python | Explicit `plan -> execute -> reflect` specialist-agent loop |
| Agent communication | A2A Protocol (v1.0) | Python | Inter-agent discovery, task delegation, structured result exchange |
| LLM | IBM Granite 4.1 8B via Ollama | — | Apache 2.0, Q4 quantized for 6GB VRAM |
| Embeddings | `granite-embedding:278m` via Ollama | — | Vector generation for semantic memory |
| Semantic memory | ChromaDB | Python | Vector storage and retrieval |
| Episodic memory | SQLite (SQLModel) | Python | Briefing history, alert history, execution logs |
| Doc processing | Docling | Python | PDF/filing parsing (feeds into Rust ingestion pipeline) |
| Task scheduling | APScheduler | Python | Cron-based briefings and watch loops |
| Web UI | Carbon React + Vite | TypeScript | Dashboard — briefings, Q&A, alerts, agent status, execution traces |
| CLI | Typer | Python | Terminal-based query, alert monitoring, quick commands |
| Observability | OpenTelemetry | Both | Full trace of every agent decision, plan execution, and data retrieval |

Stack can evolve. If a tool isn't working, flag it and we'll swap.

---

## Observability & Traceability

This is not optional — it's a core feature of Atlas. Every agent decision must be traceable.

**What gets traced (OpenTelemetry):**

- Synthesis Agent plan generation (what DAG was created and why)
- Every A2A message between agents (request, response, timing)
- Every MCP tool call (what data was requested, what was returned)
- Every reflection loop (what the agent critiqued and whether it retried)
- Guardian Agent validation results (what passed, what was flagged)
- Final output assembly (what sources contributed to each claim)

**Why this matters:** A business intelligence tool is only as trustworthy as its reasoning chain. If an analyst asks "why did Atlas flag Taiwan risk as HIGH?" — the system should produce a complete trace from raw GDELT data through agent reasoning to final assessment. No black boxes.

The Carbon web dashboard includes an **execution trace view** where the user can expand any briefing or alert and see the full agent graph, timing, sources, and confidence scores.

---

## Project Structure (As Built)

```text
atlas/
├── rust/                    ← Rust workspace: ollama-check, mcp-market-data, mcp-edgar
├── agents/                  ← Specialist agents + Agent Cards (market, geopolitical, supply_chain, research, synthesis, guardian)
├── protocols/               ← MCP client + A2A server/client/discovery
├── orchestration/           ← LangGraph graph.py, state.py
├── memory/                  ← semantic.py, episodic.py, working.py
├── ingestion/               ← seed_loader.py (Taiwan scenario → ChromaDB)
├── services/                ← llm, embeddings, briefing, alerts, scheduler
├── observability/           ← tracing, exporters, trace_reader, run_logger
├── cli/                     ← Typer CLI (`atlas`)
├── api/                     ← FastAPI streaming API (`atlas-api`, port :8787)
├── web/                     ← Carbon React dashboard (Vite dev :5173)
├── examples/                ← Demos: taiwan_demo, synthesis, briefing, alerts, tracing, _demo_infra
├── data/
│   ├── seed_data/           ← Taiwan Strait demo seed files
│   └── sample_scenarios/    ← Expected demo output reference
├── docs/                    ← ARCHITECTURE, AGENTS, PROTOCOLS, MEMORY, DATA_SOURCES, DEMO_SCRIPT, VERIFICATION, DEVLOG
├── tests/
├── scripts/
├── pyproject.toml
├── .env.example
├── README.md
└── CLAUDE.md
```

**Planned but not built:** additional Rust MCP crates (`mcp-geopolitical`, `mcp-trade`, `mcp-macro`, `mcp-gov`), full live ingestion pipeline, `compose.yml`.

---

## Build Phases

All phases **0–15 are complete** (May 2026).

| Phase | Status | Focus | Outcome | Key Decisions |
|-------|--------|-------|---------|---------------|
| 0 | ✅ | Environment setup | Ollama + Granite, LangGraph + BeeAI hello worlds, Rust toolchain, `ollama-check` | ADR-001: LangGraph; BaseAgent over BeeAI; hybrid Rust/Python |
| 1A | ✅ | Rust Ollama check | `ollama-check` binary verifies local Granite | |
| 1B | ✅ | MCP foundation | `mcp-market-data` (Yahoo Finance) on :8001, Python MCP client | ADR: MCP server pattern (Rust) |
| 2 | ✅ | Single agent PoC | Market Agent: MCP → analyze → reflect | ADR-002: Reflection loop depth |
| 3 | ✅ | A2A protocol | Agent Cards, HTTP JSON-RPC delegation | ADR-003: A2A transport |
| 4 | ✅ | Multi-agent coordination | Synthesis + LangGraph + Geopolitical + Supply Chain | ADR-004: Plan object schema |
| 5 | ✅ | Memory architecture | ChromaDB + SQLite + working memory | ADR-005: Episodic schema |
| 6 | ✅ | Research & Filing Agent | `mcp-edgar` on :8002, Research Agent | |
| 7 | ✅ | Guardian Agent | In-graph validation, confidence scoring | ADR-007: Guardian separation |
| 8 | ✅ | Scheduled briefings | `BriefingEngine`, APScheduler, briefing templates | |
| 9 | ✅ | Real-time alerts | `AlertEngine`, `AlertWatcher`, episodic alert records | |
| 10 | ✅ | Observability | OpenTelemetry tracing, trace viewer, `trace_id` in run logs | ADR-010: Trace storage |
| 11 | ✅ | CLI | Typer `atlas` command (query, briefing, alerts, status, traces) | |
| 12 | ✅ | Web dashboard | Carbon UI + FastAPI API (5 pages) | |
| 13 | ✅ | Demo scenario | Taiwan Strait end-to-end: seed data, `atlas-taiwan-demo`, DEMO_SCRIPT | |
| 14 | ✅ | Polish & presentation | Docs set, README, ruff/clippy cleanup, VERIFICATION checklist | ADR-011: Doc structure |

Phases are sequential by default but can be reordered if priorities shift. Each phase produces something runnable and testable — no big-bang integration at the end.

---

## Development Environment

| Spec | Value |
|------|-------|
| OS | Windows 11 (WSL2) |
| CPU | AMD Ryzen 7 5800H (8c/16t) |
| RAM | 16 GB |
| GPU | NVIDIA RTX 3060 6GB VRAM |
| LLM | Granite 4.1 8B Q4 via Ollama |
| Python | 3.12+ (venv) |
| Rust | stable toolchain via rustup |

**Hardware-aware design constraints:**

- 6GB VRAM = one model loaded at a time. Agents serialize through Ollama. Design agent workflows to minimize redundant LLM calls.
- 16GB RAM is tight with all services running. Embedding generation should be batched during ingestion, not on-the-fly during queries. Rust MCP servers help here — 5-20MB each vs 100-200MB for Python equivalents.
- Agent reflection loops add LLM calls — keep reflection prompts short and set retry limits (default: 2 retries per agent per task).
- Rust compile times: initial builds ~2-5 min, incremental builds ~5-15 sec. Use `cargo check` during development, `cargo build --release` for benchmarks/demo.
- For demo day: consider a cloud GPU instance (Lambda Labs, Vast.ai) to run everything simultaneously without resource contention.

---

## How to Work With Me

- **Follow the current plan** unless I say otherwise. If something in this doc conflicts with what I'm asking in conversation, the conversation wins.
- **Flag trade-offs, don't decide silently.** If a pivot has downstream consequences, surface them so I can make the call.
- **Build incrementally.** Every phase should produce something runnable and demoable. No big-bang integration at the end.
- **Assume I'm using Cursor for code execution** — give me code I can implement step by step in Agent mode with this doc as context.
- **Keep explanations tight.** I have an ISyE background, McKinsey consulting experience, and hands-on ML/LLM skills. Don't over-explain fundamentals, but do explain non-obvious architectural choices.
- **I'm learning Rust.** Explain Rust idioms and patterns when they come up. Don't assume Rust fluency — I'm building this partly to learn the language. Python is my strong side.
- **Portfolio-quality matters.** Code should be clean, documented, and structured well enough that a hiring manager or technical interviewer can read it. README, docstrings, and clear commit history are not afterthoughts.
- **Protocol implementation is the differentiator.** MCP and A2A are what set Atlas apart from generic agent projects. Get these right and everything else follows.
- **The language boundary is the second differentiator.** Rust MCP servers + Python agents is what separates this from every other LangGraph project.
- **The demo tells a story.** Every architectural decision should be visible in the Taiwan Strait demo scenario. If a feature can't be demonstrated, question whether it belongs in this phase.
- **This relates to but is separate from Enterprise Profiler.** They share some stack (Granite, ChromaDB, Docling; BeeAI only as an evaluated framework) but are independent projects with different goals. Cross-pollinate ideas where it makes sense but don't couple them.