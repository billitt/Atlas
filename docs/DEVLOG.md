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
