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
