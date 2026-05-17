# CLAUDE.md — Code Context for Claude

This file is maintained by Cursor after each phase. Claude reads it to understand the codebase without re-reading every file. **Cursor: update this file at the end of every phase.**

Last updated: Phase 3 (2026-05-17)

---

## Codebase Metrics

| Metric | Value |
|--------|-------|
| Commits | 11 |
| Total files | 57 |
| Rust LOC | 599 |
| Python LOC | 1,224 |
| Phases complete | 0, 1A, 1B, 2, 3 |

---

## Architecture Summary

```
User query
  → Synthesis Agent (Phase 4 — not yet built)
    → A2A discovery (protocols/a2a/discovery.py)
    → A2A tasks/send (protocols/a2a/client.py)
      → Market Agent (agents/market/agent.py) — REAL, plan/execute/reflect
        → MCP client (protocols/mcp/client.py)
          → Rust MCP server (rust/mcp-market-data/) on :8001
            → Yahoo Finance API
        → Granite via Ollama (services/llm.py)
      → Geopolitical Agent (agents/geopolitical/agent.py) — STUB, canned response
      → Supply Chain Agent — NOT YET BUILT
    → A2A server per agent (protocols/a2a/server.py) on :9001, :9002
```

---

## File Map

### Rust — Data Layer

**rust/Cargo.toml** — Workspace root. Members: ollama-check, mcp-market-data.

**rust/ollama-check/src/main.rs** (130 lines)
- Phase 1A. Health check binary.
- GET /api/tags → list models, POST /api/generate → test prompt.
- Crates: reqwest, serde, serde_json, tokio.
- Entry: `#[tokio::main] async fn main() -> ExitCode`

**rust/mcp-market-data/src/main.rs** (78 lines)
- Phase 1B. Axum server on port 8001.
- Routes: GET /health, POST /mcp.
- AppState holds reqwest::Client.
- Delegates to mcp::handle_json_rpc.

**rust/mcp-market-data/src/mcp.rs** (164 lines)
- MCP JSON-RPC 2.0 router.
- Methods: initialize, tools/list, tools/call.
- tools/call routes to yahoo::fetch_quote for "get_quote" tool.
- Structs: JsonRpcRequest, ToolsCallParams.
- Helpers: json_rpc_success(), json_rpc_error().

**rust/mcp-market-data/src/yahoo.rs** (227 lines)
- Yahoo Finance chart API client.
- fetch_quote(client, symbol) → Result<Quote, String>.
- Calls: GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d
- Quote struct: symbol, regular_market_price, previous_close, change_percent, currency, regular_market_volume.
- quote_to_text(quote) → pretty JSON string for MCP content block.

### Python — Intelligence Layer

**services/llm.py** (56 lines)
- Central LLM config. Reads OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL from .env.
- get_chat_ollama() → ChatOllama (LangChain).
- chat(prompt) → str (single-turn via LangChain).
- ollama_generate(prompt) → str (raw HTTP to Ollama /api/generate).
- list_models() → list[str] (GET /api/tags).
- Constants: OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, BEEAI_MODEL_NAME.

**protocols/mcp/client.py** (100 lines)
- McpClient class. Constructor takes base_url.
- _request(method, params) → sends JSON-RPC 2.0 POST to {base_url}/mcp.
- initialize() → handshake.
- list_tools() → list of tool defs.
- call_tool(name, arguments) → tool result dict.
- Uses httpx.AsyncClient.

**protocols/a2a/server.py** (209 lines)
- A2AServer class. Wraps any BaseAgent + agent_card.json.
- Runs on configurable port via uvicorn or similar.
- GET /.well-known/agent.json → serves Agent Card.
- POST /a2a → JSON-RPC 2.0: agent/card, tasks/send.
- tasks/send runs agent.run(query), returns A2A artifact.

**protocols/a2a/client.py** (82 lines)
- A2AClient class.
- discover(url) → fetch Agent Card from /.well-known/agent.json.
- send_task(url, message) → POST tasks/send, return result.
- Uses httpx.AsyncClient.

**protocols/a2a/discovery.py** (69 lines)
- AgentRegistry class.
- register(card) → add to registry.
- discover_all() → all registered cards.
- find_by_skill(skill_id) → agents with matching skill.
- load_from_files() → scans agents/*/agent_card.json.

**agents/base.py** (82 lines)
- BaseAgent ABC.
- Abstract methods: plan(query), execute(query, plan), reflect(query, draft).
- run(query) → plan → execute → reflect loop with max_retries (default 2).
- AgentResult TypedDict: analysis, sources, confidence.
- Confidence = Literal["HIGH", "MEDIUM", "LOW"].

**agents/market/agent.py** (237 lines)
- MarketIntelligenceAgent(BaseAgent).
- plan(): LLM call #1 — Granite decides which MCP tools to call. Returns list of tool_calls.
- execute(): MCP fetches via market_tools + LLM call #2 — Granite analyzes real data.
- reflect(): LLM call #3 — Granite critiques grounding. Returns (passed, feedback, confidence).
- _parse_json_from_llm() — extracts JSON from fenced or raw LLM output.
- _fallback_symbol_from_query() — extracts ticker if LLM JSON fails.
- Uses services.llm.chat() for all Granite calls.
- Uses protocols.mcp.client.McpClient for MCP calls.

**agents/market/tools.py** (58 lines)
- AVAILABLE_TOOLS global list, populated from MCP server.
- load_tools(client) → calls initialize + list_tools on MCP server.
- call_get_quote(client, symbol) → calls get_quote tool, parses response.
- extract_text_content(mcp_result) → pulls text from MCP content blocks.
- format_tools_for_prompt() → JSON string of tools for LLM prompt.

**agents/geopolitical/agent.py** (44 lines)
- GeopoliticalRiskAgent(BaseAgent). STUB.
- Returns canned risk assessment, does not call any MCP server.
- Confidence always MEDIUM.

**agents/market/agent_card.json** (27 lines)
- Skills: market_snapshot, anomaly_scan, correlation_check.
- URL: http://localhost:9001.

**agents/geopolitical/agent_card.json** (27 lines)
- Skills: risk_assessment, event_timeline, entity_exposure.
- URL: http://localhost:9002.

### Examples / Scripts

**scripts/verify_ollama.py** (45 lines) — Ollama health check.
**examples/langgraph_hello.py** (43 lines) — Phase 0 LangGraph verification.
**examples/beeai_hello.py** (28 lines) — Phase 0 BeeAI verification.
**examples/market_agent_demo.py** (46 lines) — Phase 2 Market Agent end-to-end.
**examples/a2a_demo.py** (87 lines) — Phase 3 A2A discovery + task delegation.

### Config

**pyproject.toml** — hatchling build, deps: langgraph, langchain-ollama, beeai-framework, a2a-sdk, mcp, httpx, chromadb, sqlmodel, docling, apscheduler, streamlit, typer, feedparser, opentelemetry-api/sdk, python-dotenv. Dev: pytest, ruff. Packages: services, examples, scripts, agents, protocols.
**.env.example** — OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, LLM_CHAT_MODEL_NAME, BEEAI_LOG_LEVEL.
**.gitignore** — .venv/, __pycache__/, .env, data/chroma/, data/sqlite/, *.db, rust/target/, PRD.md.

---

## Phase Changelog

### Phase 0 — Environment Setup
- Python venv, pip install -e ".[dev]"
- Ollama 0.24.0 + ibm/granite4.1:8b pulled
- services/llm.py, scripts/verify_ollama.py
- examples/langgraph_hello.py, examples/beeai_hello.py
- Full directory scaffold with __init__.py stubs

### Phase 1A — Rust ollama-check
- rust/Cargo.toml workspace
- rust/ollama-check/ — binary mirrors verify_ollama.py
- Crates: reqwest, serde, serde_json, tokio
- Ownership error fix: let response = response.error_for_status()?;

### Phase 1B — Rust MCP Market Data Server
- rust/mcp-market-data/ — axum server on :8001
- 3 Rust files: main.rs (server), mcp.rs (JSON-RPC), yahoo.rs (Yahoo Finance)
- MCP methods: initialize, tools/list, tools/call (get_quote)
- protocols/mcp/client.py — Python MCP client
- Cross-language boundary proven: Python → HTTP → Rust → Yahoo Finance

### Phase 2 — Market Intelligence Agent
- agents/base.py — BaseAgent ABC with plan/execute/reflect loop
- agents/market/agent.py — 3 LLM calls: plan tools, analyze data, reflect on grounding
- agents/market/tools.py — MCP tool helpers
- examples/market_agent_demo.py — end-to-end demo
- ADR-002: Reflection loop depth (max 2 retries)

### Phase 3 — A2A Protocol Layer
- protocols/a2a/server.py — A2A HTTP server wrapping any agent
- protocols/a2a/client.py — async A2A client (discover, send_task)
- protocols/a2a/discovery.py — Agent Card registry
- agents/market/agent_card.json, agents/geopolitical/agent_card.json
- agents/geopolitical/agent.py — stub agent
- examples/a2a_demo.py — discovery + task delegation demo
- ADR-003: HTTP JSON-RPC chosen over gRPC

---

## Dependencies Between Files

```
examples/market_agent_demo.py
  → agents/market/agent.py
    → agents/base.py
    → agents/market/tools.py
      → protocols/mcp/client.py (HTTP to Rust MCP server)
    → services/llm.py (Granite via Ollama)

examples/a2a_demo.py
  → protocols/a2a/server.py
    → agents/market/agent.py (or any BaseAgent)
  → protocols/a2a/client.py
  → protocols/a2a/discovery.py
    → agents/*/agent_card.json
```

---

## Ports

| Port | Service | Status |
|------|---------|--------|
| 11434 | Ollama | Required always |
| 8001 | Rust mcp-market-data | Required for Market Agent |
| 9001 | A2A Market Agent | Phase 3+ |
| 9002 | A2A Geopolitical Agent | Phase 3+ (stub) |
| 9003 | A2A Supply Chain Agent | Not yet |

---

## What's Stubbed / Not Yet Built

- agents/supply_chain/ — empty __init__.py only
- agents/research/ — empty __init__.py only
- agents/synthesis/ — empty __init__.py only
- agents/guardian/ — empty __init__.py only
- orchestration/ — empty __init__.py only
- memory/ — empty __init__.py only
- ingestion/ — empty __init__.py only
- observability/ — empty __init__.py only
- ui/ — empty __init__.py only
- cli/ — empty __init__.py only
- All Rust MCP servers except mcp-market-data