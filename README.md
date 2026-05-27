# Atlas

**A local-first, protocol-native AI intelligence system: Rust MCP data services + Python A2A agents + LangGraph orchestration + Granite on Ollama.**

Atlas is a local-first global intelligence platform built around protocol-native AI agents. It combines Rust data services, Python agent orchestration, MCP tool access, A2A agent-to-agent delegation, LangGraph workflows, and IBM Granite running locally through Ollama.

The project is designed as a portfolio-grade demonstration of hybrid Rust + Python systems, agentic AI architecture, reflection loops, and open-source/on-prem inference.

See [docs/DEVLOG.md](docs/DEVLOG.md) for implementation notes and ADRs. See [CLAUDE.md](CLAUDE.md) for detailed file-level context.

## Current Status

Phases **0–12 are implemented and demo-verified**.

| Phase | Status | What Works |
|-------|--------|------------|
| 0 | Complete | Python environment, Ollama, Granite, LangGraph hello world, BeeAI evaluated via hello world |
| 1A | Complete | Rust `ollama-check` binary verifies local Ollama + Granite |
| 1B | Complete | Rust MCP market-data server serves Yahoo Finance quotes on port `8001` |
| 2 | Complete | Market Intelligence Agent: query → plan → MCP fetch → analyze → reflect |
| 3 | Complete | A2A Agent Cards, discovery, HTTP JSON-RPC delegation |
| 4 | Complete | Synthesis Agent coordinates four specialist agents through LangGraph + A2A |
| 5 | Complete | Three-tier memory: ChromaDB semantic, SQLite episodic, in-context working |
| 6 | Complete | Research & Filing Agent + Rust EDGAR MCP server on port `8002` |
| 7 | Complete | Guardian Agent validates grounding and confidence in the synthesis graph |
| 8 | Complete | Scheduled briefings via `BriefingEngine` and APScheduler |
| 9 | Complete | Real-time alert monitoring via `AlertEngine` and `AlertWatcher` |
| 10 | Complete | OpenTelemetry tracing across graph, agents, MCP, A2A, briefings, and alerts |
| 11 | Complete | Typer CLI (`atlas`) for query, briefing, alerts, status, traces, and history |
| 12 | Complete | Streamlit web dashboard (`atlas-dashboard`) with query, briefings, alerts, status, traces |

## Architecture Snapshot

```text
User (Typer CLI `atlas` / Streamlit dashboard `atlas-dashboard`)
  -> LangGraph Synthesis workflow (or BriefingEngine / AlertEngine)
  -> Synthesis Agent creates execution plan with Granite
  -> A2A delegates tasks to specialist agents
  -> Market Agent (:9001) -> Rust MCP market data (:8001) -> Yahoo Finance
  -> Geopolitical Agent (:9002) -> Granite model knowledge
  -> Supply Chain Agent (:9003) -> Granite model knowledge
  -> Research & Filing Agent (:9004) -> Rust MCP EDGAR (:8002) -> SEC APIs
  -> Semantic + Episodic memory (ChromaDB + SQLite)
  -> Granite synthesizes unified briefing
  -> Guardian Agent validates claims and confidence (in-graph quality gate)
  -> Run logger + episodic persistence
```

### Framework Roles

| Layer | Technology | Role |
|-------|------------|------|
| Local LLM runtime | Ollama | Hosts and runs `ibm/granite4.1:8b` |
| LLM | IBM Granite 4.1 8B | Planning, analysis, reflection, synthesis, validation |
| Orchestration | LangGraph | Traceable workflow: plan → delegate → synthesize → guardian |
| Agent delegation | A2A-style HTTP JSON-RPC | Agent discovery and `tasks/send` delegation |
| Tool/data protocol | MCP-style HTTP JSON-RPC | Market and EDGAR agents call Rust tools through `/mcp` |
| Data layer | Rust + Axum | MCP market-data and EDGAR servers |
| Memory | ChromaDB + SQLite | Semantic vectors, episodic briefing/alert records |
| Agent layer | Python | Specialist agents, protocol clients, synthesis, alerts |
| Scheduling | APScheduler | Autonomous daily/weekly/custom briefings |
| Market data | Yahoo Finance chart API | Live quote and volume baseline data |
| Filing data | SEC EDGAR APIs | Company filings, full-text search |

## Runtime Services

| Service | Port | Started By | Purpose |
|---------|------|------------|---------|
| Ollama | `11434` | Ollama app / CLI | Runs Granite locally |
| Rust MCP market data | `8001` | `cargo run -p mcp-market-data` | Serves `get_quote` tool |
| Rust MCP EDGAR | `8002` | `cargo run -p mcp-edgar` | Serves `company_filings`, `filing_text`, `full_text_search` |
| Market A2A Agent | `9001` | Demo scripts | Market Intelligence Agent endpoint |
| Geopolitical A2A Agent | `9002` | Demo scripts | Model-knowledge geopolitical analysis |
| Supply Chain A2A Agent | `9003` | Demo scripts | Model-knowledge supply-chain analysis |
| Research A2A Agent | `9004` | Demo scripts | SEC filing analysis |
| Guardian Agent | `9005` | In-graph only | Agent Card reserved; validation runs in LangGraph |

## Setup

### Prerequisites

- Python 3.11+
- Rust stable toolchain
- [Ollama](https://ollama.com/download)
- NVIDIA GPU recommended for Granite 4.1 8B Q4 (~5.3 GB VRAM)

### Pull Granite

```powershell
ollama pull ibm/granite4.1:8b
```

If `ollama` is not on PATH on Windows:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull ibm/granite4.1:8b
```

### Install Python Package

```powershell
cd atlas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Verify Ollama + Granite

```powershell
python -m scripts.verify_ollama
python -m examples.langgraph_hello
python -m examples.beeai_hello
```

Entry points after installation:

```powershell
atlas-verify-ollama
atlas-langgraph-hello
atlas-beeai-hello
atlas-memory-demo
atlas-synthesis-demo
atlas-edgar-demo
atlas-guardian-demo
atlas-briefing-demo
atlas-scheduler-demo
atlas-alert-demo
atlas-alert-watch-demo
atlas-tracing-demo
atlas
atlas-dashboard
```

## Web Dashboard

Launch the Streamlit dashboard:

```powershell
atlas-dashboard
# or: streamlit run ui/streamlit_app.py
```

Opens a dark-themed wide-layout app at `http://localhost:8501` with five pages:

| Page | Purpose |
|------|---------|
| **Query** | Natural-language synthesis with Guardian verdict, sources, trace link |
| **Briefings** | Generate daily/weekly/custom briefings; browse episodic history |
| **Alerts** | Check rules, optional watch loop, alert history feed |
| **Agent Status** | Ollama, MCP, A2A agent cards, memory stats grid |
| **Trace Viewer** | Browse `data/traces/` span trees with duration highlighting |

The sidebar shows live system status (Ollama, MCP, memory counts) and auto-starts A2A agents on first load. Query and Briefing pages require Ollama + MCP servers; other pages degrade gracefully with warnings.

**Visual layout:** dark background, colored confidence badges (green/yellow/red), bordered agent cards, expandable analysis sections, and dataframe history tables.

## CLI Usage

After `pip install -e ".[dev]"`, the `atlas` command is available:

```powershell
# System health
atlas status

# Natural-language query (Ollama + MCP required; auto-starts A2A agents)
atlas query "What's the TSMC risk exposure?"

# Scheduled-style briefings
atlas briefing --type daily
atlas briefing --type weekly
atlas briefing --topics "semiconductors,trade tensions"

# Alerts
atlas alerts rules
atlas alerts check
atlas alerts watch --interval 300

# History and traces
atlas history --limit 10
atlas traces list
atlas traces show <trace_id>
```

**Prerequisites for query/briefing:** Ollama running, `cargo run -p mcp-market-data` and `cargo run -p mcp-edgar`. The CLI auto-starts A2A agent servers in the background.

Optional tracing: `$env:OTEL_EXPORT_TO = "file"` before `atlas query ...` exports spans to `data/traces/`.

## Phase-by-Phase Implementation

### Phase 0 — Environment Setup

Verified the Python environment and local LLM stack: Ollama, Granite, LangGraph hello world, BeeAI evaluation. Production agents use the custom `BaseAgent` plan → execute → reflect pattern.

Key files: `services/llm.py`, `scripts/verify_ollama.py`, `examples/langgraph_hello.py`

### Phase 1A — Rust Ollama Health Check

Rust workspace binary that verifies Ollama + Granite from Rust.

```powershell
cd atlas\rust
cargo run -p ollama-check
```

### Phase 1B — Rust MCP Market Data Server

Axum MCP server on `:8001` with `get_quote` tool backed by Yahoo Finance.

```powershell
cd atlas\rust
cargo run -p mcp-market-data
```

### Phase 2 — Market Intelligence Agent

First specialist agent: Granite plans MCP tool calls, analyzes live Yahoo data, reflects on grounding.

```powershell
# Terminal 1: cargo run -p mcp-market-data
# Terminal 2: python -m examples.market_agent_demo
```

### Phase 3 — A2A Protocol Layer

Agent Cards, discovery, HTTP JSON-RPC `tasks/send` delegation.

```powershell
# Terminal 1: cargo run -p mcp-market-data
# Terminal 2: python -m examples.a2a_demo
```

### Phase 4 — Multi-Agent Coordination

Synthesis Agent + LangGraph orchestrates Market, Geopolitical, and Supply Chain agents over A2A.

```powershell
# Terminals: Ollama, cargo run -p mcp-market-data, cargo run -p mcp-edgar
python -m examples.synthesis_demo
```

### Phase 5 — Memory Architecture

Three-tier memory: ChromaDB semantic vectors, SQLite episodic records, in-context working scratchpad.

```powershell
python -m examples.memory_demo
```

### Phase 6 — Research & Filing Agent + EDGAR MCP

Rust EDGAR MCP server on `:8002`; Research Agent fetches SEC filings and ingests text into semantic memory.

```powershell
# Terminal 1: cargo run -p mcp-edgar
python -m examples.edgar_demo
```

### Phase 7 — Guardian Agent

In-graph validator checks claim grounding, source freshness, and confidence; retries synthesis once on LOW confidence.

```powershell
python -m examples.guardian_demo
```

### Phase 8 — Scheduled Briefings

`BriefingEngine` runs the full synthesis + Guardian pipeline over a watchlist; `AtlasScheduler` automates cadence.

```powershell
# Terminals: Ollama, MCP servers
python -m examples.briefing_demo          # one immediate briefing
python -m examples.scheduler_demo         # autonomous 60s cadence for 3 min
```

### Phase 9 — Real-time Alerts

`AlertEngine` evaluates MCP fresh data against Granite JSON conditions; `AlertWatcher` polls on an interval.

```powershell
# Terminals: Ollama, MCP servers
python -m examples.alert_demo             # one-shot rule check
python -m examples.alert_watch_demo       # 60s watch loop for 3 min
```

### Phase 10 — OpenTelemetry Tracing

Full execution traces for synthesis, briefings, and alerts. File export to `data/traces/`.

```powershell
python -m examples.tracing_demo
# or: atlas-tracing-demo
```

### Phase 11 — Typer CLI

The CLI replaces example scripts for day-to-day use. See [CLI Usage](#cli-usage) above.

### Phase 12 — Streamlit Web Dashboard

Visual interface over the same pipelines. See [Web Dashboard](#web-dashboard) above.

```powershell
atlas-dashboard
```

## Full Chain of Command

```text
1. User runs a demo (synthesis, briefing, scheduler, or alert)
2. Demo verifies MCP servers, starts four specialist A2A servers
3. LangGraph runs plan -> delegate -> synthesize -> guardian
4. Synthesis Agent asks Granite to create an execution plan
5. A2A client sends each task to the right specialist agent
6. Market Agent calls Rust MCP :8001 for live Yahoo data
7. Research Agent calls Rust MCP :8002 for SEC filings
8. Geopolitical and Supply Chain agents analyze with model knowledge
9. Semantic and episodic memory enrich context and persist results
10. Granite synthesizes a unified briefing with sources and confidence
11. Guardian validates claims; synthesis retries once if confidence is LOW
12. Run logger writes JSON artifact; episodic memory stores the record
```

## Current Demo Scenario

The synthesis demo runs the Taiwan Strait semiconductor exposure scenario:

```text
What's the exposure risk if Taiwan Strait tensions escalate?
Consider semiconductor supply chains and market impact.
```

Output includes geopolitical risk, supply-chain dependencies, live market data, SEC filing context (when Research is invoked), execution plan, per-agent sources, Guardian validation, and overall confidence.

## Architecture Decisions

See [docs/DEVLOG.md](docs/DEVLOG.md) for the full ADR text.

| ADR | Phase | Decision |
|-----|-------|----------|
| ADR-001 | 0 | LangGraph orchestration; BeeAI evaluated, BaseAgent chosen for production agents |
| ADR-002 | 2 | Reflection loop depth and retry policy |
| ADR-003 | 3 | A2A transport: HTTP JSON-RPC 2.0 over gRPC for now |
| ADR-004 | 4 | Explicit DAG-shaped plan object schema |
| ADR-005 | 5 | Episodic memory schema design |
| ADR-007 | 7 | Guardian separation of concerns and retry policy |

## Next Phases

Planned next:

- Phase 12: Web dashboard (Streamlit trace viewer)
- Phase 13: Full demo scenario
- Phase 14: Polish and presentation

## Notes

- Geopolitical and Supply Chain agents use Granite model knowledge only; live MCP data sources for those domains are not yet built.
- Rust MCP servers must be running before demos that require live market or filing data.
- Ollama must be running before any Granite-backed agent call.
- Multi-agent demos and the CLI share startup helpers in `examples/_demo_infra.py` (CLI auto-starts A2A servers for query/briefing).
