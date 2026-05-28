# Atlas

**A local-first, protocol-native AI intelligence system: Rust MCP data services + Python A2A agents + LangGraph orchestration + Granite on Ollama.**

## Quick Start

Five commands from clone to running the Taiwan Strait demo:

```powershell
git clone <repo-url> atlas && cd atlas
python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -e ".[dev]"
ollama pull ibm/granite4.1:8b
# Terminal A: cd rust && cargo run -p mcp-market-data
# Terminal B: cd rust && cargo run -p mcp-edgar
atlas-taiwan-demo
```

Prerequisites: Python 3.11+, Rust stable, [Ollama](https://ollama.com/download). Ollama must be running before the demo. Full setup: [Setup](#setup) below.

---

## What Makes This Different

| Differentiator | Detail |
|----------------|--------|
| **Rust + Python polyglot** | Rust owns data fetching (MCP servers); Python owns agent reasoning and orchestration |
| **Protocol-native** | MCP for agent↔data, A2A for agent↔agent — not a monolithic prompt chain |
| **Reflection at every agent** | Plan → execute → reflect loop on all specialists; failed audits trigger retry |
| **Full OpenTelemetry tracing** | Every LLM call, MCP fetch, and A2A delegation is a span with `trace_id` linkage |
| **On-prem, zero cloud** | Granite via Ollama, ChromaDB, SQLite — no API keys or cloud LLM dependencies |

Atlas is a portfolio-grade demonstration of hybrid systems, agentic AI architecture, and auditable intelligence pipelines.

**Documentation:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/AGENTS.md](docs/AGENTS.md) · [docs/PROTOCOLS.md](docs/PROTOCOLS.md) · [docs/MEMORY.md](docs/MEMORY.md) · [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · [docs/VERIFICATION.md](docs/VERIFICATION.md)

See [docs/DEVLOG.md](docs/DEVLOG.md) for ADRs. See [CLAUDE.md](CLAUDE.md) for file-level context.

---

## Current Status

Phases **0–14 are complete**. All components are implemented and demo-verified.

| Phase | Status | What Works |
|-------|--------|------------|
| 0 | Complete | Python environment, Ollama, Granite, LangGraph hello world |
| 1A | Complete | Rust `ollama-check` binary |
| 1B | Complete | Rust MCP market-data server on `:8001` |
| 2 | Complete | Market Intelligence Agent |
| 3 | Complete | A2A Agent Cards, discovery, HTTP JSON-RPC delegation |
| 4 | Complete | Synthesis Agent + LangGraph multi-agent coordination |
| 5 | Complete | Three-tier memory: ChromaDB, SQLite, working scratchpad |
| 6 | Complete | Research & Filing Agent + EDGAR MCP on `:8002` |
| 7 | Complete | Guardian Agent in-graph validation |
| 8 | Complete | Scheduled briefings via `BriefingEngine` + APScheduler |
| 9 | Complete | Real-time alerts via `AlertEngine` + `AlertWatcher` |
| 10 | Complete | OpenTelemetry tracing across all pipelines |
| 11 | Complete | Typer CLI (`atlas`) |
| 12 | Complete | Streamlit dashboard (`atlas-dashboard`) |
| 13 | Complete | Taiwan Strait end-to-end demo scenario |
| 14 | Complete | Polish, documentation, verification checklist |

---

## Project Structure

```text
atlas/
├── agents/           # Specialist agents (market, geopolitical, supply_chain, research, synthesis, guardian)
├── cli/              # Typer CLI (`atlas query`, `atlas status`, etc.)
├── ui/               # Streamlit dashboard pages
├── orchestration/    # LangGraph synthesis workflow
├── protocols/        # MCP client + A2A server/client/discovery
├── memory/           # Semantic (ChromaDB), episodic (SQLite), working
├── services/         # LLM, briefings, alerts, scheduler, embeddings
├── ingestion/        # Seed data loader (Taiwan scenario)
├── observability/    # OpenTelemetry tracing, run logger, trace reader
├── examples/         # Demos including `taiwan_demo.py` and shared `_demo_infra.py`
├── rust/             # MCP servers: mcp-market-data, mcp-edgar, ollama-check
├── data/
│   ├── seed_data/    # Taiwan Strait demo seed files
│   └── sample_scenarios/  # Expected demo output reference
├── docs/             # Architecture, agents, protocols, memory, demo script
└── runs/             # JSON run artifacts (gitignored)
```

---

## Taiwan Strait Demo

The flagship scenario exercises every Atlas path in one narrative:

```powershell
atlas-taiwan-demo
```

Interview walkthrough: **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**

Equivalent after seeding:

```powershell
atlas query "What's the exposure risk if Taiwan Strait tensions escalate? Consider semiconductor supply chains, market impact, and TSMC filing risk factors."
atlas-dashboard   # Query page with the same question
```

Expected output: [data/sample_scenarios/taiwan_demo_expected_output.md](data/sample_scenarios/taiwan_demo_expected_output.md)

---

## Architecture Snapshot

```text
User (CLI / Dashboard / demos)
  -> LangGraph: plan -> delegate -> synthesize -> guardian
  -> Market :9001 -> MCP :8001 -> Yahoo Finance
  -> Geopolitical :9002 -> semantic memory (seed GDELT)
  -> Supply Chain :9003 -> semantic memory (seed trade flow)
  -> Research :9004 -> MCP :8002 -> SEC EDGAR
  -> ChromaDB + SQLite memory
  -> OpenTelemetry traces + run logs
```

Full diagram: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Runtime Services

| Service | Port | Start |
|---------|------|-------|
| Ollama | `11434` | `ollama serve` |
| MCP market data | `8001` | `cargo run -p mcp-market-data` |
| MCP EDGAR | `8002` | `cargo run -p mcp-edgar` |
| A2A agents | `9001`–`9004` | Auto-started by CLI/demos |

---

## Setup

### Prerequisites

- Python 3.11+
- Rust stable toolchain
- [Ollama](https://ollama.com/download)
- NVIDIA GPU recommended for Granite 4.1 8B Q4 (~5.3 GB VRAM)

### Install

```powershell
cd atlas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ollama pull ibm/granite4.1:8b
ollama pull granite-embedding:278m
```

### Verify

```powershell
atlas-verify-ollama
atlas status
```

---

## CLI Usage

```powershell
atlas status
atlas query "What's the TSMC risk exposure?"
atlas briefing --type daily
atlas alerts check
atlas history --limit 10
atlas traces list
atlas traces show <trace_id>
```

**Prerequisites for query/briefing:** Ollama + both MCP servers. CLI auto-starts A2A agents.

---

## Web Dashboard

```powershell
atlas-dashboard
```

Opens at `http://localhost:8501` — Query, Briefings, Alerts, Agent Status, Trace Viewer.

---

## Entry Points

```powershell
atlas                    # Main CLI
atlas-dashboard          # Streamlit UI
atlas-taiwan-demo        # Full Taiwan Strait scenario
atlas-synthesis-demo     # Multi-agent synthesis
atlas-tracing-demo       # OpenTelemetry trace demo
atlas-briefing-demo      # Scheduled briefing
atlas-alert-demo         # One-shot alert check
```

Full list in `pyproject.toml` `[project.scripts]`.

---

## Architecture Decisions

| ADR | Phase | Decision |
|-----|-------|----------|
| ADR-001 | 0 | LangGraph orchestration; BaseAgent for specialists |
| ADR-002 | 2 | Reflection loop depth and retry policy |
| ADR-003 | 3 | A2A transport: HTTP JSON-RPC 2.0 |
| ADR-004 | 4 | Explicit DAG-shaped plan object schema |
| ADR-005 | 5 | Episodic memory schema design |
| ADR-007 | 7 | Guardian separation and retry policy |
| ADR-010 | 10 | Trace storage and retention |
| ADR-011 | 14 | Documentation structure for interviews |

Full ADR text: [docs/DEVLOG.md](docs/DEVLOG.md)

---

## Notes

- Geopolitical and Supply Chain agents use seed data in semantic memory; live MCP feeds are future work.
- Rust MCP servers must run before queries requiring live market or filing data.
- Verification checklist: [docs/VERIFICATION.md](docs/VERIFICATION.md)
