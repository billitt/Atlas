# Atlas Verification Checklist

Commands and expected outcomes for pre-interview verification. Run from the project root with venv activated.

---

## Prerequisites

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ollama pull ibm/granite4.1:8b
ollama pull granite-embedding:278m
```

Terminal 1: `cd rust && cargo run -p mcp-market-data`  
Terminal 2: `cd rust && cargo run -p mcp-edgar`  
Terminal 3: `cd rust && cargo run -p mcp-trade` (optional `ATLAS_COMTRADE_API_KEY` in `.env`)  
Ollama must be running.

---

## Static Checks

| Command | Expected |
|---------|----------|
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | All files formatted (or run `ruff format .`) |
| `cd rust && cargo check --all` | Finished successfully |
| `cd rust && cargo clippy --all -- -W clippy::all` | Finished, no warnings |
| `cd rust && cargo fmt --all -- --check` | No diff (or run `cargo fmt --all`) |
| `cd rust && cargo test -p mcp-common -p mcp-market-data` | All unit tests passed |
| `pytest tests/ -q` | All boundary tests passed (no Ollama/MCP required) |

### Import smoke tests

```powershell
python -c "from cli.main import app; print('cli ok')"
python -c "from api.main import create_app; print('api ok')"
python -c "from examples.taiwan_demo import main; print('taiwan ok')"
python -c "from ingestion.seed_loader import load_taiwan_scenario; print('ingestion ok')"
python -c "from orchestration import build_synthesis_graph, run_synthesis_graph; print('orchestration ok')"
python -c "from protocols.mcp import McpClient; print('mcp ok')"
```

All should print `ok` without import errors.

---

## Runtime Commands

### `atlas status`

When everything is running, expect:

- Ollama: reachable, Granite model listed
- MCP market `:8001`: healthy
- MCP EDGAR `:8002`: healthy
- MCP trade `:8003`: healthy (or reported down if server not started)
- Semantic memory: document count ≥ 0
- Episodic memory: briefing/alert counts
- Last briefing/alert timestamps (if any prior runs)

When MCP is down, status reports failures without crashing.

### `atlas query "What's the TSMC risk exposure?"`

- Auto-starts A2A agents on ports 9001–9004
- Runs LangGraph synthesis pipeline
- Prints combined analysis, confidence, Guardian verdict
- Writes `runs/YYYYMMDD_HHMMSS.json`
- Duration: ~2–6 minutes (hardware dependent)

### `atlas-taiwan-demo`

Six steps:

| Step | Expected output |
|------|-----------------|
| 1. Seed | `Ingested 12 documents into semantic memory` |
| 2. Alert | `ALERT [HIGH] Taiwan Strait tension spike` |
| 3. Synthesis | Multi-agent briefing, `trace_id` printed |
| 4. Briefing | Summary line + `baseline created` delta |
| 5. Trace | Span tree with 25–60 spans |
| 6. Summary | `ATLAS TAIWAN STRAIT DEMO — EXERCISED` box |

Total duration: ~5–12 minutes.

### Web dashboard (dev)

```powershell
atlas-api
# separate terminal:
cd web && npm run dev
```

- UI at `http://127.0.0.1:5173`, API at `http://127.0.0.1:8787`
- Five pages load: Query, Briefings, Alerts, Agent Status, Trace Viewer
- Status endpoint: `GET /api/status`

Production: `cd web && npm run build`, then `$env:ATLAS_API_PRODUCTION = "1"; atlas-api` → `http://127.0.0.1:8787`

### Other entry points

| Command | Produces |
|---------|----------|
| `atlas briefing --type daily` | Multi-topic briefing via BriefingEngine |
| `atlas alerts check` | Evaluates default alert rules |
| `atlas alerts rules` | Lists registered rules |
| `atlas history --limit 5` | Recent BriefingRecord rows |
| `atlas traces list` | Trace files in `data/traces/` |
| `atlas traces show <id>` | Formatted span tree |

---

## Demo Script Reference

Full walkthrough: [DEMO_SCRIPT.md](DEMO_SCRIPT.md)  
Expected shapes: [../data/sample_scenarios/taiwan_demo_expected_output.md](../data/sample_scenarios/taiwan_demo_expected_output.md)

---

## Security Smoke Tests (Phase 15)

With MCP servers running (`cargo run -p mcp-market-data`, `cargo run -p mcp-edgar`, `cargo run -p mcp-trade`):

| Check | Command / action | Expected |
|-------|------------------|----------|
| Localhost bind | `netstat -an \| findstr "8001 8002 8003"` | `LISTENING` on `127.0.0.1:8001`, `:8002`, `:8003` |
| Default auth off | `curl http://127.0.0.1:8001/health` | `{"status":"ok"}` |
| Auth enabled | Set `ATLAS_MCP_AUTH_TOKEN=test` and restart MCP; `curl` without header | HTTP 401 |
| Auth client | Same env; `McpClient` with matching token in `.env` | `initialize()` succeeds |
| Invalid symbol | MCP `get_quote` with `../../etc` | JSON-RPC error, no Yahoo call |
| Rate limit | Set `ATLAS_RATE_LIMIT_RPS=2`; burst >2 requests/sec | HTTP 429 |
| Rust unit tests | `cd rust && cargo test -p mcp-common` | 6 tests passed |
| API bind | `atlas-api`; check netstat | `127.0.0.1:8787` only |

See [SECURITY.md](SECURITY.md) for configuration details.

---

## Known Limitations

| Limitation | Detail |
|------------|--------|
| **Single GPU serialization** | Ollama processes one Granite request at a time; multi-agent demos queue LLM calls |
| **16 GB RAM constraint** | Granite 4.1 8B Q4 (~5.3 GB VRAM) + ChromaDB + agents fit consumer hardware; tight on 8 GB systems |
| **Simulated geopolitical data** | GDELT-style seed in ChromaDB; no live GDELT MCP |
| **Comtrade API key optional** | `mcp-trade` preview mode caps at 500 records without `ATLAS_COMTRADE_API_KEY` |
| **Yahoo unofficial API** | Market quotes depend on Yahoo chart endpoint stability |
| **SEC rate limits** | 125 ms delay per EDGAR call; bulk ingestion is slow |
| **No cloud fallback** | All inference is on-prem; no API keys or cloud LLM |

---

## Commit History Notes

Phase progression is clear in git log. A few early commits use vague messages (not rewritten):

| Commit | Message | Note |
|--------|---------|------|
| `e8e613b` | Refactor | Phase 9.1 cleanup (`_demo_infra`, run logger) |
| `358f9df` | Log Files | Phase 5 observability additions |
| `444662c` | documentation adjustment | Early docs |
| `e279975` | Updating PRD | PRD edits |
| `85e3b3f` | finalizing Phase 0 | Phase 0 wrap-up |

Phase-titled commits (`Phase N: ...`) tell the implementation story from Phase 0 through Phase 13.

---

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design overview |
| [AGENTS.md](AGENTS.md) | Per-agent reference |
| [PROTOCOLS.md](PROTOCOLS.md) | MCP + A2A details |
| [MEMORY.md](MEMORY.md) | Three-tier memory |
| [DATA_SOURCES.md](DATA_SOURCES.md) | MCP servers and seed data |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Interview walkthrough |
| [DEVLOG.md](DEVLOG.md) | Phase history and ADRs |
| [SECURITY.md](SECURITY.md) | Production hardening |
