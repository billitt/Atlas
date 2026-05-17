# Atlas Development Log

Step-by-step record of build progress and architecture decision records (ADRs).

---

## Phase 0 — Environment setup (2026-05-16)

**Goal:** Ollama + Granite running, LangGraph + BeeAI installed, project scaffolded.

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

## ADR-001: LangGraph orchestration + BeeAI per-agent construction

**Status:** Accepted (Phase 0)

**Context:** Atlas needs multi-agent coordination with explicit state (DAGs, retries, HITL) and individual agents that benefit from Granite-native tool calling.

**Decision:**

- **LangGraph** — orchestration layer: workflow graphs, shared state, conditional routing between agents.
- **BeeAI** — individual agent construction where it fits (tool-calling patterns, per-agent logic).

**Consequences:**

- Synthesis/orchestration code lives under `orchestration/` (LangGraph).
- Specialist agents live under `agents/*` (BeeAI + MCP tools).
- Both frameworks call the same Granite model via Ollama (`services/llm.py`).
- On 6GB VRAM, agents must serialize through Ollama; reflection loops need tight retry limits.

**Alternatives considered:** Pure BeeAI orchestration — rejected for weaker explicit DAG/state story needed for demo traceability.

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
