# Atlas

Local-first multi-agent intelligence demo: Rust MCP data servers, Python A2A specialists, LangGraph synthesis, Granite on Ollama.

## Quick Start

Five commands from clone to running the Taiwan Strait demo:

```powershell
git clone <repo-url> atlas && cd atlas
python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -e ".[dev]"
ollama pull ibm/granite4.1:8b
# Terminal A: cd rust && cargo run -p mcp-market-data
# Terminal B: cd rust && cargo run -p mcp-edgar
# Terminal C: cd rust && cargo run -p mcp-trade
atlas-taiwan-demo
```

Prerequisites: Python 3.11+, Rust stable, [Ollama](https://ollama.com/download). Ollama must be running before the demo. Full setup: [Setup](#setup) below.

---

## Architecture

| Layer | Role |
|-------|------|
| Rust MCP (`:8001`–`:8003`) | Market quotes, SEC EDGAR, UN Comtrade |
| Python specialists (`:9001`–`:9004`) | Plan → execute → reflect; delegate via A2A |
| LangGraph + Synthesis | DAG plan, merge, Guardian validation |
| Memory | ChromaDB semantic, SQLite episodic |
| UI | Typer CLI or Carbon web UI + FastAPI (`atlas-api`) |

Query streaming uses **HTTP SSE**, not WebSockets. Docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/AGENTS.md](docs/AGENTS.md) · [docs/PROTOCOLS.md](docs/PROTOCOLS.md) · [docs/MEMORY.md](docs/MEMORY.md) · [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · [docs/VERIFICATION.md](docs/VERIFICATION.md) · [docs/DEVLOG.md](docs/DEVLOG.md) · [CLAUDE.md](CLAUDE.md)

---

## Current Status

Phases **0–16** implemented. Taiwan Strait demo exercises the full stack.

| Phase | Focus |
|-------|--------|
| 0–5 | Environment, MCP market data, agents, A2A, memory |
| 6–7 | EDGAR MCP, Research agent, Guardian |
| 8–9 | Scheduled briefings, alerts |
| 10–11 | OpenTelemetry, Typer CLI |
| 12 | Carbon web UI + FastAPI (replaced Streamlit) |
| 13–14 | Taiwan demo, docs, verification |
| 15 | Localhost bind, optional auth, rate limits |
| 16 | `mcp-trade` Comtrade MCP, live Supply Chain agent |

---

## Project Structure

```text
atlas/
├── agents/           # Specialist agents (market, geopolitical, supply_chain, research, synthesis, guardian)
├── cli/              # Typer CLI (`atlas query`, `atlas status`, etc.)
├── api/              # FastAPI streaming API (`atlas-api`)
├── web/              # Carbon React dashboard (Vite)
├── orchestration/    # LangGraph synthesis workflow
├── protocols/        # MCP client + A2A server/client/discovery
├── memory/           # Semantic (ChromaDB), episodic (SQLite), working
├── services/         # LLM, briefings, alerts, scheduler, embeddings
├── ingestion/        # Seed data loader (Taiwan scenario)
├── observability/    # OpenTelemetry tracing, run logger, trace reader
├── examples/         # Demos including `taiwan_demo.py` and shared `_demo_infra.py`
├── rust/             # MCP servers: mcp-market-data, mcp-edgar, mcp-trade, ollama-check
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
# Or use the web UI Query page with the same question (see Web Dashboard below)
```

Expected output: [data/sample_scenarios/taiwan_demo_expected_output.md](data/sample_scenarios/taiwan_demo_expected_output.md)

---

## Architecture Snapshot

```text
User (CLI / Carbon web UI / demos)
  -> LangGraph: plan -> delegate -> synthesize -> guardian
  -> Market :9001 -> MCP :8001 -> Yahoo Finance
  -> Geopolitical :9002 -> semantic memory (seed GDELT)
  -> Supply Chain :9003 -> MCP :8003 (UN Comtrade) + ChromaDB cache
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
| MCP trade (UN Comtrade) | `8003` | `cargo run -p mcp-trade` |
| A2A agents | `9001`–`9004` | Auto-started by CLI/API/demos |
| Atlas API | `8787` | `atlas-api` |
| Vite dev UI | `5173` | `cd web && npm run dev` |

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
copy .env.example .env   # set ATLAS_COMTRADE_API_KEY for keyed Comtrade (optional)
```

Set `ATLAS_COMTRADE_API_KEY` in `.env` for full Comtrade access (100k records/call). The Rust `mcp-trade` server loads this via `dotenvy`; blank falls back to keyless preview (500 records).

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

**Prerequisites for query/briefing:** Ollama + all three MCP servers (`:8001`–`:8003`). CLI/API auto-start A2A agents on `:9001`–`:9004`.

---

## Web Dashboard

Development (API + Vite dev server with hot reload):

```powershell
# Terminal C: MCP servers + Ollama already running
atlas-api
# Terminal D:
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173` — Query, Briefings, Alerts, Agent Status, Trace Viewer. Vite proxies `/api` and `/health` to the API on `:8787`.

Production (single process serves API + built static UI):

```powershell
cd web && npm run build
$env:ATLAS_API_PRODUCTION = "1"
atlas-api
```

Open `http://127.0.0.1:8787`.

---

## Entry Points

```powershell
atlas                    # Main CLI
atlas-api                # FastAPI server (web UI backend)
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
| ADR-012 | 15 | Security hardening model |
| ADR-013 | 16 | Live Comtrade MCP + Supply Chain cache |

Full ADR text: [docs/DEVLOG.md](docs/DEVLOG.md)

---

## License

Licensed under the MIT License — see [LICENSE](LICENSE).

---

## Notes

- **Geopolitical:** GDELT-style seed in semantic memory; live GDELT MCP not built.
- **Supply Chain:** Live UN Comtrade via `mcp-trade` (`:8003`); ChromaDB cache on success; preview mode without API key.
- **Research:** Model picks which filing to open from EDGAR list; analysis must not invent text when filing body was not fetched.
- **Web UI sources:** Normalized in `api/routes/query.py` (Comtrade cache vs EDGAR vs market).
- Run logs: `runs/`; verification: [docs/VERIFICATION.md](docs/VERIFICATION.md)
