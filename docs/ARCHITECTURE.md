# Atlas Architecture

Concise system design reference for interviews. Read time: ~5 minutes.

---

## System Overview

Atlas is a **local-first intelligence platform** that combines a Rust data layer with a Python agent layer. Users interact via CLI, Carbon web UI, or demo scripts. All reasoning runs on **IBM Granite via Ollama** — no cloud LLM dependencies.

```text
┌─────────────────────────────────────────────────────────────────┐
│  User interfaces: Typer CLI · Carbon web UI · demo scripts      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Orchestration: LangGraph (plan → delegate → synthesize → guardian)│
│  Synthesis Agent + Guardian Agent                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ A2A HTTP JSON-RPC
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Market :9001      Geopolitical :9002     Supply Chain :9003
        │                    │                    │
        │ MCP                │ Semantic           │ Semantic
        ▼                    ▼                    ▼
   Rust :8001           ChromaDB seed         ChromaDB seed
   (Yahoo)              (GDELT-style)         (trade flow)
        │
   Research :9004 ──MCP──► Rust :8002 (SEC EDGAR)
        │
        ▼
   Memory: ChromaDB (semantic) + SQLite (episodic) + working scratchpad
        │
        ▼
   Observability: OpenTelemetry spans → data/traces/ + runs/ JSON logs
```

---

## Language Boundary

| Layer | Language | Responsibility |
|-------|----------|----------------|
| **Data services** | Rust (Axum) | HTTP MCP servers, external API clients, rate limiting, parsing |
| **Intelligence** | Python | Agents, orchestration, memory, CLI, API |
| **Inference** | Ollama (Granite) | Planning, analysis, reflection, synthesis, validation |

**Why split?** Rust handles I/O-bound, latency-sensitive data fetching with strong typing and predictable resource use. Python owns agent logic, LangGraph workflows, and rapid iteration on prompts and protocols. The boundary is **MCP over HTTP JSON-RPC** — Python never calls Yahoo or SEC directly for production paths.

---

## Protocol Decisions

### MCP (Model Context Protocol style)

- **Role:** Agent ↔ data
- **Transport:** HTTP POST `/mcp` with JSON-RPC 2.0
- **Implementation:** Rust Axum servers expose `initialize`, `tools/list`, `tools/call`
- **Why:** Standardized tool surface; agents discover capabilities at runtime; data layer is swappable without changing agent code

### A2A (Agent-to-Agent style)

- **Role:** Agent ↔ agent
- **Transport:** HTTP POST `/a2a` with JSON-RPC 2.0; Agent Cards at `/.well-known/agent.json`
- **Implementation:** Python `A2AServer` / `A2AClient`; Synthesis delegates via `tasks/send`
- **Why:** Specialist agents are independently deployable; Synthesis plans a DAG and delegates without monolithic prompts

**Together:** MCP gives each agent *tools*; A2A gives the orchestrator *delegates*. Market Agent uses MCP for quotes; Synthesis uses A2A to ask Market to analyze a query.

See [PROTOCOLS.md](PROTOCOLS.md) for implementation details.

---

## Memory Tiers

| Tier | Store | Purpose |
|------|-------|---------|
| **Semantic** | ChromaDB (`data/chroma`) | Vector search over documents, filings, seed scenario data |
| **Episodic** | SQLite (`data/sqlite/`) | Append-only audit trail: briefings, alerts, agent executions |
| **Working** | In-process dict | Per-query scratchpad during LangGraph state |

Semantic memory is queried **during agent execution** (Market, Geopolitical, Supply Chain, Research). Episodic memory enables **temporal reasoning** — delta from last briefing, confidence history, alert history.

See [MEMORY.md](MEMORY.md) for schemas and examples.

---

## Agent Design Pattern

Every specialist agent extends `BaseAgent` with a **plan → execute → reflect** loop:

1. **Plan** — Granite produces a structured plan (JSON)
2. **Execute** — Fetch data (MCP and/or semantic memory), analyze with Granite
3. **Reflect** — Granite audits the draft for grounding and limitation disclosure

Failed reflection triggers retry (up to `max_retries`, default 2). This is ADR-002.

**Guardian** is different: it does not plan or execute. It validates the *synthesized* briefing after all specialists complete (ADR-007).

**Synthesis** does not extend `BaseAgent`. It plans a multi-agent DAG, delegates via A2A, merges results, and calls Granite for the unified briefing.

See [AGENTS.md](AGENTS.md) for per-agent details.

---

## Key Workflows

### Ad-hoc query

`atlas query` → LangGraph → four specialists → synthesize → Guardian → run log + episodic record

### Scheduled briefing

`BriefingEngine` → same pipeline per watchlist topic → delta from last briefing

### Real-time alert

`AlertEngine` → fresh MCP data → Granite JSON condition → episodic alert record

### Taiwan Strait demo

Seed loader → semantic memory → alert + synthesis + briefing + trace (see [DEMO_SCRIPT.md](DEMO_SCRIPT.md))

---

## Observability

OpenTelemetry spans cover graph nodes, agent phases, LLM calls, MCP tool calls, and A2A delegation. Traces export to `data/traces/`; run logs in `runs/` link via `trace_id`.

---

## Related Docs

- [SECURITY.md](SECURITY.md) — production hardening and network exposure
- [AGENTS.md](AGENTS.md) — specialist agent reference
- [PROTOCOLS.md](PROTOCOLS.md) — MCP and A2A implementation
- [MEMORY.md](MEMORY.md) — three-tier memory
- [DATA_SOURCES.md](DATA_SOURCES.md) — MCP servers and seed data
- [DEVLOG.md](DEVLOG.md) — ADRs and phase history
