# Atlas — Global Intelligence Platform | Project Context

You are helping build **Atlas**, a global business intelligence system powered by autonomous AI agents that communicate via industry-standard protocols. This document is the current plan and master reference point. Follow it as the default source of truth, but be ready to pivot on any decision — architecture, tooling, sequencing, agent design — if the conversation calls for it. Nothing here is sacred except the core goal.

---

## Core Goal

Build a system where specialized AI agents continuously gather, analyze, and synthesize global business intelligence — financial markets, geopolitical signals, trade and supply chain data, public filings, and news — into a unified knowledge base that a user can query in plain English, receive scheduled briefings from, and get real-time alerts when conditions change.

This is a **portfolio project** designed to demonstrate mastery of:

- Agentic AI architecture using emerging industry standards (MCP, A2A)
- Multi-agent orchestration with explicit state management (LangGraph)
- RAG pipelines with three-tier memory architecture
- Reflection and self-correction patterns
- Full observability and decision traceability
- Production-grade engineering on a fully open-source, on-prem stack

It should be impressive enough to walk through in a technical interview at any top-tier AI or tech company. The demo tells a story, not just "here's a chatbot."

---

## Hard Constraints

These don't change without explicit discussion:

- **100% open source.** Zero proprietary dependencies. Every component must be Apache 2.0, MIT, or equivalent. No OpenAI, no Claude API, no paid services.
- **On-prem / air-gapped capable.** The system must run entirely on local hardware with no external API calls required at runtime. Data ingestion can pull from the internet, but inference and analysis must be self-contained.
- **Single-user demo target.** Auth and multi-tenancy are out of scope. The system is optimized for one analyst operating it locally.
- **Protocol-native.** All data source connections use MCP. All inter-agent communication uses A2A. No ad-hoc integration patterns.

---

## Architecture Overview

Atlas is built on two industry-standard protocols that separate tool connectivity from agent coordination:

**MCP (Model Context Protocol)** — Anthropic's open standard for connecting agents to tools and data sources. Every external data adapter in Atlas (FRED, EDGAR, GDELT, Yahoo Finance, etc.) is implemented as an MCP server. This means any MCP-compatible client can plug into Atlas's data layer. We're building infrastructure, not a closed system. MCP is governed by the Linux Foundation's Agentic AI Foundation (AAIF) and is adopted by every major AI provider.

**A2A (Agent-to-Agent Protocol)** — Google's open standard for inter-agent communication. Atlas agents discover each other's capabilities through Agent Cards, delegate tasks via the protocol, and exchange structured results over HTTP with JSON-RPC 2.0. A2A reached v1.0 in early 2026 with support for gRPC and signed Agent Cards. This means a third-party agent could theoretically be plugged into the Atlas system and participate without modification.

**LangGraph** — The orchestration layer. Agent workflows are modeled as directed graphs with explicit state, conditional routing, retry logic, and human-in-the-loop checkpoints. The Synthesis Agent's execution plan is itself a DAG — fully traceable in OpenTelemetry.

**BeeAI** — Used for individual agent construction where it provides a natural fit, particularly for agents that benefit from IBM Granite's native tool-calling patterns. BeeAI handles per-agent logic; LangGraph handles the coordination graph between agents.

```
                    ┌─────────────────┐
                    │      User       │
                    │  (CLI / Web UI) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   LangGraph     │
                    │  Orchestrator   │
                    │  (DAG planner)  │
                    └────────┬────────┘
                             │ A2A Protocol
          ┌──────────────────┼──────────────────┐
          │                  │                  │
  ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │   Market     │  │  Geopolitical│  │ Supply Chain │
  │   Intel      │  │  Risk        │  │ & Trade      │
  │   Agent      │  │  Agent       │  │ Agent        │
  └───────┬──────┘  └───────┬──────┘  └───────┬──────┘
          │                  │                  │
          │    MCP Protocol  │   MCP Protocol   │
          │                  │                  │
  ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
  │ FRED, Yahoo  │  │ GDELT, RSS   │  │ Comtrade,    │
  │ Finance,     │  │ UN/WTO,      │  │ BIS, USITC,  │
  │ Alpha Vant.  │  │ Gov releases │  │ Port data    │
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
- MCP servers: FRED, Yahoo Finance, Alpha Vantage (free tier), EDGAR
- Capabilities: Anomaly detection, trend shift identification, cross-asset correlation, technical indicator calculation
- Reflection: Validates that claims are grounded in data, checks for stale data, confirms statistical significance before surfacing signals
- A2A Agent Card: Advertises capabilities like `market_snapshot`, `anomaly_scan`, `correlation_check`

**Geopolitical Risk Agent**

- Domain: Conflicts, sanctions, elections, policy shifts, trade agreements
- MCP servers: GDELT, ACLED, RSS feeds (Reuters, AP, government releases), UN/WTO
- Capabilities: Event detection, entity extraction (NER), regional risk scoring, temporal trend analysis
- Reflection: Cross-references multiple sources before assigning risk scores, flags single-source assessments, checks recency
- A2A Agent Card: Advertises `risk_assessment`, `event_timeline`, `entity_exposure`

**Supply Chain & Trade Agent**

- Domain: Global trade flows, tariffs, shipping disruptions, commodity dependencies
- MCP servers: UN Comtrade, WTO datasets, BIS, USITC, port/shipping open data
- Capabilities: Dependency graph construction, tariff impact modeling, disruption detection, chokepoint identification
- Reflection: Validates trade flow data against multiple sources, checks for data lag, confirms causal chains before asserting disruption impact
- A2A Agent Card: Advertises `dependency_map`, `disruption_alert`, `tariff_impact`

**Research & Filing Agent**

- Domain: SEC filings, earnings reports, annual reports, regulatory filings
- MCP servers: SEC EDGAR, Open Corporates, government data portals
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

**Semantic Memory (ChromaDB)** Long-term knowledge store. All ingested documents, filings, news articles, and market data are chunked, embedded (Granite Embedding English R2), and stored as vectors. This is the RAG retrieval layer — agents query it for relevant context when answering questions or generating assessments.

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

Example flow: Trade Agent detects new tariff announcement affecting semiconductor imports → fires A2A task to Geopolitical Agent for context → fires A2A task to Market Agent for price impact → Synthesis Agent compiles alert with full reasoning chain → alert delivered to CLI and dashboard simultaneously.

---

## Demo Scenario (The Story)

The end-to-end demo walks through a single compelling scenario that exercises every agent, both protocols, all three memory tiers, and the full observability stack:

**Trigger:** Taiwan Strait tensions spike (simulated via injected GDELT data)

1. **Geopolitical Risk Agent** detects elevated conflict signals in GDELT feed via MCP → runs NER, identifies entities → self-reflects on source diversity → assigns risk score → publishes assessment via A2A
2. **Supply Chain Agent** receives A2A task → queries UN Comtrade via MCP for semiconductor trade flow data → builds dependency graph → identifies EU/US exposure → self-reflects on data freshness → publishes via A2A
3. **Market Intelligence Agent** receives A2A task → pulls TSMC, ASML, Intel pricing from Yahoo Finance via MCP → detects correlated movement → self-reflects on statistical significance → publishes via A2A
4. **Research Agent** receives A2A task → pulls latest TSMC 20-F from EDGAR via MCP → extracts risk factor language about geopolitical exposure → self-reflects on selective quoting risk → publishes via A2A
5. **Synthesis Agent** collects all outputs → resolves conflicting signals → generates structured briefing with reasoning chain → self-reflects on plan completeness
6. **Guardian Agent** validates all claims trace to sources → assigns confidence levels → flags any unsupported assertions
7. **Alert fires** to CLI terminal with summary and link to full briefing
8. **Dashboard** displays full reasoning chain, source citations, agent execution graph (via OpenTelemetry traces), and confidence heat map

An interviewer watching this demo sees: protocol-native architecture (MCP + A2A), multi-agent coordination with explicit planning, reflection at every stage, three-tier memory in action, full observability, and a real-world scenario that matters.

---

## Data Sources (Open & Free)

All sources are implemented as MCP servers — standardized, pluggable, and independently testable.


| Category             | MCP Server         | Sources                                        |
| -------------------- | ------------------ | ---------------------------------------------- |
| Financial markets    | `mcp-market-data`  | Yahoo Finance, FRED, Alpha Vantage (free tier) |
| Corporate filings    | `mcp-edgar`        | SEC EDGAR full-text search + filing API        |
| Geopolitical events  | `mcp-geopolitical` | GDELT, ACLED, RSS feeds (Reuters, AP)          |
| Government / policy  | `mcp-gov`          | UN, WTO, government press releases             |
| Trade & supply chain | `mcp-trade`        | UN Comtrade, WTO datasets, BIS, USITC          |
| Macro indicators     | `mcp-macro`        | World Bank Open Data, IMF, OECD, BLS           |


All sources must be publicly accessible with no API key required, or free-tier API keys only.

---

## Tech Stack


| Layer               | Tool                          | Role                                                                                |
| ------------------- | ----------------------------- | ----------------------------------------------------------------------------------- |
| Agent orchestration | LangGraph                     | DAG-based workflow coordination, state management, conditional routing, retry logic |
| Agent construction  | BeeAI                         | Individual agent logic, Granite-native tool calling                                 |
| Agent communication | A2A Protocol (v1.0)           | Inter-agent discovery, task delegation, structured result exchange                  |
| Tool connectivity   | MCP                           | Standardized agent-to-data-source interface                                         |
| LLM                 | IBM Granite 4.1 8B via Ollama | Apache 2.0, Q4 quantized for 6GB VRAM                                               |
| Embeddings          | Granite Embedding English R2  | Vector generation for semantic memory                                               |
| Semantic memory     | ChromaDB                      | Vector storage and retrieval                                                        |
| Episodic memory     | SQLite (SQLModel)             | Briefing history, alert history, execution logs                                     |
| Doc processing      | Docling                       | PDF/filing parsing and chunking                                                     |
| Task scheduling     | APScheduler                   | Cron-based briefings and watch loops                                                |
| Web UI              | Streamlit                     | Dashboard — briefings, Q&A, alerts, agent status, execution traces                  |
| CLI                 | Typer                         | Terminal-based query, alert monitoring, quick commands                              |
| Data fetching       | httpx + feedparser            | Per-MCP-server adapters                                                             |
| Observability       | OpenTelemetry                 | Full trace of every agent decision, plan execution, and data retrieval              |


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

The Streamlit dashboard includes an **execution trace view** where the user can expand any briefing or alert and see the full agent graph, timing, sources, and confidence scores.

---

## Project Structure

```
atlas/
├── agents/                         ← Agent definitions
│   ├── base.py                     ← Common agent pattern (plan → execute → reflect)
│   ├── market/
│   │   ├── agent.py                ← Market Intelligence Agent
│   │   ├── tools.py                ← Agent-specific tool definitions
│   │   └── agent_card.json         ← A2A capability advertisement
│   ├── geopolitical/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── agent_card.json
│   ├── supply_chain/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── agent_card.json
│   ├── research/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── agent_card.json
│   ├── synthesis/
│   │   ├── agent.py                ← Orchestrator with DAG planner
│   │   ├── planner.py              ← Explicit plan generation and evaluation
│   │   └── agent_card.json
│   └── guardian/
│       ├── agent.py                ← Second-pass validator
│       └── agent_card.json
│
├── protocols/
│   ├── a2a/                        ← A2A protocol implementation
│   │   ├── server.py               ← A2A HTTP/JSON-RPC server
│   │   ├── client.py               ← A2A client for agent-to-agent calls
│   │   └── discovery.py            ← Agent Card registry and discovery
│   └── mcp/                        ← MCP server implementations
│       ├── market_data.py          ← Yahoo Finance, FRED, Alpha Vantage
│       ├── edgar.py                ← SEC EDGAR
│       ├── geopolitical.py         ← GDELT, ACLED, RSS
│       ├── trade.py                ← UN Comtrade, WTO, BIS
│       ├── macro.py                ← World Bank, IMF, OECD
│       └── gov.py                  ← Government releases, UN/WTO docs
│
├── orchestration/
│   ├── graph.py                    ← LangGraph workflow definitions
│   ├── state.py                    ← Shared state schemas
│   └── router.py                   ← Query routing and plan dispatch
│
├── memory/
│   ├── semantic.py                 ← ChromaDB interface (long-term knowledge)
│   ├── episodic.py                 ← SQLite interface (historical events/logs)
│   └── working.py                  ← Per-query scratchpad management
│
├── ingestion/
│   ├── pipeline.py                 ← Document loading, chunking, embedding
│   └── schedulers.py               ← Cron jobs for periodic data pulls
│
├── services/
│   ├── llm.py                      ← Ollama / Granite wrapper
│   └── embeddings.py               ← Embedding service
│
├── observability/
│   ├── tracing.py                  ← OpenTelemetry setup and span definitions
│   └── exporters.py                ← Trace export config (Jaeger, console, file)
│
├── ui/
│   ├── streamlit_app.py            ← Web dashboard entry point
│   └── pages/
│       ├── briefings.py            ← Scheduled briefing viewer
│       ├── query.py                ← Natural language Q&A interface
│       ├── alerts.py               ← Real-time alert feed
│       ├── agent_status.py         ← Agent health and capability view
│       └── trace_viewer.py         ← Execution trace and reasoning chain explorer
│
├── cli/
│   └── main.py                     ← Typer CLI for queries, alerts, status
│
├── data/
│   ├── sample_scenarios/           ← Demo scenario data (Taiwan Strait, etc.)
│   └── seed_data/                  ← Initial knowledge base seeding
│
├── docs/
│   ├── DEVLOG.md                   ← Step-by-step dev log + ADRs
│   ├── ARCHITECTURE.md             ← System design, protocol decisions
│   ├── AGENTS.md                   ← Agent specs, reflection patterns, Agent Cards
│   ├── PROTOCOLS.md                ← MCP + A2A implementation details
│   ├── DATA_SOURCES.md             ← Source documentation and schemas
│   ├── MEMORY.md                   ← Three-tier memory architecture
│   └── DEMO_SCRIPT.md             ← Step-by-step demo walkthrough
│
├── tests/
│   ├── agents/                     ← Per-agent unit tests
│   ├── protocols/                  ← MCP server and A2A protocol tests
│   ├── memory/                     ← Memory tier tests
│   └── integration/                ← End-to-end scenario tests
│
├── compose.yml                     ← Local multi-service setup
├── .env.example
└── README.md

```

---

## Build Phases


| Phase | Focus                    | Outcome                                                                                                        | Key Decisions                               |
| ----- | ------------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| 0     | Environment setup        | Ollama + Granite running, LangGraph + BeeAI installed, project scaffolded                                      | ADR: LangGraph vs pure BeeAI orchestration  |
| 1     | MCP foundation           | First MCP server (Yahoo Finance) operational, returns structured data                                          | ADR: MCP server implementation pattern      |
| 2     | Single agent PoC         | Market Intelligence Agent can ingest via MCP, embed to ChromaDB, answer queries with self-reflection           | ADR: Reflection loop depth and retry limits |
| 3     | A2A protocol layer       | A2A server running, Agent Cards published, two agents can discover and delegate tasks                          | ADR: A2A transport choice (HTTP vs gRPC)    |
| 4     | Multi-agent coordination | Add Geopolitical + Supply Chain agents, Synthesis Agent routes between them via A2A with explicit plan objects | ADR: Plan object schema                     |
| 5     | Memory architecture      | Three-tier memory operational — semantic (ChromaDB), episodic (SQLite), working (in-context)                   | ADR: Episodic memory schema design          |
| 6     | Research & Filing Agent  | SEC EDGAR MCP server, document processing pipeline, filing diff detection                                      |                                             |
| 7     | Guardian Agent           | Second-pass validation, confidence scoring, hallucination detection against source data                        | ADR: Confidence threshold calibration       |
| 8     | Scheduled briefings      | APScheduler cron jobs, briefing templates, episodic memory logging                                             |                                             |
| 9     | Real-time alerts         | Watch loops on MCP servers, threshold detection, multi-agent alert assembly                                    |                                             |
| 10    | Observability            | Full OpenTelemetry tracing across all agents, plans, and protocol calls                                        | ADR: Trace storage and retention            |
| 11    | CLI interface            | Typer-based terminal Q&A, alert stream, agent status                                                           |                                             |
| 12    | Web dashboard            | Streamlit UI — briefings, Q&A, alerts, agent status, trace viewer                                              |                                             |
| 13    | Demo scenario            | Taiwan Strait scenario fully wired, seed data loaded, demo script written                                      |                                             |
| 14    | Polish & presentation    | README, documentation, code cleanup, commit history, walkthrough rehearsal                                     |                                             |


Phases are sequential by default but can be reordered if priorities shift. Each phase produces something runnable and testable — no big-bang integration at the end.

---

## Development Environment


| Spec | Value                        |
| ---- | ---------------------------- |
| OS   | Windows 11 (WSL2)            |
| CPU  | AMD Ryzen 7 5800H (8c/16t)   |
| RAM  | 16 GB                        |
| GPU  | NVIDIA RTX 3060 6GB VRAM     |
| LLM  | Granite 4.1 8B Q4 via Ollama |


**Hardware-aware design constraints:**

- 6GB VRAM = one model loaded at a time. Agents serialize through Ollama. Design agent workflows to minimize redundant LLM calls.
- 16GB RAM is tight with all services running. Embedding generation should be batched during ingestion, not on-the-fly during queries.
- Agent reflection loops add LLM calls — keep reflection prompts short and set retry limits (default: 2 retries per agent per task).
- For demo day: consider a cloud GPU instance (Lambda Labs, [Vast.ai](http://Vast.ai)) to run everything simultaneously without resource contention.

---

## How to Work With Me

- **Follow the current plan** unless I say otherwise. If something in this doc conflicts with what I'm asking in conversation, the conversation wins.
- **Flag trade-offs, don't decide silently.** If a pivot has downstream consequences, surface them so I can make the call.
- **Build incrementally.** Every phase should produce something runnable and demoable. No big-bang integration at the end.
- **Assume I'm using Cursor for code execution** — give me code I can implement step by step in Agent mode with this doc as context.
- **Keep explanations tight.** I have an ISyE background, McKinsey consulting experience, and hands-on ML/LLM skills. Don't over-explain fundamentals, but do explain non-obvious architectural choices.
- **Portfolio-quality matters.** Code should be clean, documented, and structured well enough that a hiring manager or technical interviewer can read it. README, docstrings, and clear commit history are not afterthoughts.
- **Protocol implementation is the differentiator.** MCP and A2A are what set Atlas apart from generic agent projects. Get these right and everything else follows.
- **The demo tells a story.** Every architectural decision should be visible in the Taiwan Strait demo scenario. If a feature can't be demonstrated, question whether it belongs in this phase.
- **This relates to but is separate from Enterprise Profiler.** They share some stack (Granite, ChromaDB, BeeAI, Docling) but are independent projects with different goals. Cross-pollinate ideas where it makes sense but don't couple them.

