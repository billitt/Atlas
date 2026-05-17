# CLAUDE.md — Code Context for Claude

This file is maintained by Cursor after each phase. Claude reads it to understand the codebase without re-reading every file. **Cursor: update this file at the end of every phase.**

Last updated: Phase 5 (2026-05-17)

---

## Codebase Metrics

| Metric | Value |
|--------|-------|
| Commits | 13 |
| Total files | 72 |
| Rust LOC | 615 |
| Python LOC | 2,545 |
| Phases complete | 0, 1A, 1B, 2, 3, 4, 5 |

---

## Architecture Summary

```text
User query
  -> LangGraph Synthesis workflow (orchestration/graph.py)
    -> Synthesis Agent (agents/synthesis/agent.py)
      -> Planner (agents/synthesis/planner.py) creates DAG plan from Agent Cards
      -> A2A client (protocols/a2a/client.py) delegates tasks/send
        -> Market Agent :9001 (agents/market/agent.py)
          -> Semantic Memory (memory/semantic.py, ChromaDB data/chroma)
          -> MCP client (protocols/mcp/client.py)
            -> Rust MCP server :8001 (rust/mcp-market-data/)
              -> Yahoo Finance API
          -> Granite via Ollama (services/llm.py)
          -> Episodic Memory execution log (memory/episodic.py, SQLite)
        -> Geopolitical Agent :9002 (agents/geopolitical/agent.py)
          -> Granite model-knowledge analysis, explicit live-data limitation
        -> Supply Chain Agent :9003 (agents/supply_chain/agent.py)
          -> Granite model-knowledge analysis, explicit live-data limitation
      -> Synthesis Agent queries Episodic Memory for similar briefings
      -> Granite synthesizes unified briefing
      -> Run Logger writes runs/YYYYMMDD_HHMMSS.json
      -> Episodic Memory writes BriefingRecord

Memory tiers:
  Tier 1 Semantic: ChromaDB persistent vectors in data/chroma
  Tier 2 Episodic: SQLite records in data/sqlite/atlas_episodic.db
  Tier 3 Working: in-context scratchpad (memory/working.py), used by demos/LangGraph state
```

---

## File Map

### Rust — Data Layer

**rust/Cargo.toml** — Workspace root. Members: `ollama-check`, `mcp-market-data`.

**rust/ollama-check/src/main.rs**
- Phase 1A health check binary.
- `#[tokio::main] async fn main() -> ExitCode`
- `async fn run() -> Result<(), Box<dyn std::error::Error>>`
- `async fn list_models(client: &reqwest::Client, base_url: &str) -> Result<Vec<String>, Box<dyn std::error::Error>>`
- `async fn generate(client: &reqwest::Client, base_url: &str, prompt: &str) -> Result<String, Box<dyn std::error::Error>>`

**rust/mcp-market-data/src/main.rs**
- Axum server on port `8001`.
- Routes: `GET /health`, `POST /mcp`.
- `async fn main()`
- `async fn health() -> Json<serde_json::Value>`
- `async fn mcp_endpoint(State(state): State<AppState>, Json(request): Json<JsonRpcRequest>) -> Json<serde_json::Value>`

**rust/mcp-market-data/src/mcp.rs**
- MCP-style JSON-RPC 2.0 router.
- Methods: `initialize`, `tools/list`, `tools/call`.
- `pub async fn handle_json_rpc(state: AppState, request: JsonRpcRequest) -> Json<Value>`
- `fn handle_initialize(params: Option<Value>) -> Result<Value, (i32, String)>`
- `fn handle_tools_list() -> Result<Value, (i32, String)>`
- `async fn handle_tools_call(state: &AppState, params: Option<Value>) -> Result<Value, (i32, String)>`

**rust/mcp-market-data/src/yahoo.rs**
- Yahoo Finance chart API client.
- `pub async fn fetch_quote(client: &reqwest::Client, symbol: &str) -> Result<Quote, String>`
- `pub fn quote_to_text(quote: &Quote) -> String`
- Uses `range=1d` for latest price/previous close and `range=1mo` for volume baselines.
- `Quote`: `symbol`, `regular_market_price`, `previous_close`, `change_percent`, `currency`, `regular_market_volume`, `previous_day_volume`, `average_volume_5d`, `volume_vs_average_percent`.

### Services

**services/llm.py**
- Central Granite/Ollama chat config.
- Constants: `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `BEEAI_MODEL_NAME`.
- `def get_chat_ollama(**kwargs: Any) -> ChatOllama`
- `def chat(prompt: str) -> str`
- `def ollama_generate(prompt: str, *, model: str | None = None) -> str`
- `def list_models() -> list[str]`

**services/embeddings.py** (52 lines)
- Ollama embedding wrapper for semantic memory.
- Constants: `OLLAMA_EMBED_MODEL`.
- `def embed_texts(texts: list[str]) -> list[list[float]]`
- `def _embed_with_model(texts: list[str], model: str) -> list[list[float]]`
- Calls `POST /api/embed` with `OLLAMA_EMBED_MODEL`, falls back to `OLLAMA_CHAT_MODEL`.

### Memory

**memory/semantic.py** (94 lines)
- ChromaDB semantic memory.
- `class SemanticMemory`
- `__init__(collection_name: str = "atlas", persist_dir: str = "data/chroma") -> None`
- `add_documents(texts: list[str], metadatas: list[dict[str, Any]], ids: list[str]) -> None`
- `query(text: str, n_results: int = 5) -> list[dict[str, Any]]`
- `count() -> int`
- Helper: `_chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]`
- Dependencies: `chromadb.PersistentClient`, `services.embeddings.embed_texts`.

**memory/episodic.py** (157 lines)
- SQLite + SQLModel episodic memory.
- DB path: `data/sqlite/atlas_episodic.db`.
- Tables:
  - `BriefingRecord`: `id`, `timestamp`, `query`, `plan`, `agent_results`, `final_briefing`, `confidence`, `sources`, `trace_id`, `duration_seconds`.
  - `AlertRecord`: `id`, `timestamp`, `trigger`, `agent_chain`, `assessment`, `severity`.
  - `AgentExecution`: `id`, `timestamp`, `agent_name`, `task`, `result`, `confidence`, `duration_seconds`.
- `class EpisodicMemory`
- `__init__(db_path: str = DB_PATH) -> None`
- `init_db() -> None`
- `log_briefing(run_data: dict[str, Any]) -> BriefingRecord`
- `log_agent_execution(agent_name: str, task: str, result: dict[str, Any], confidence: str, duration: float | None) -> AgentExecution`
- `query_briefings(query: str, limit: int = 10) -> list[BriefingRecord]`
- `query_briefings_by_date(start: datetime, end: datetime) -> list[BriefingRecord]`
- `get_confidence_history(topic: str, days: int = 90) -> list[dict[str, Any]]`
- `briefing_count() -> int`

**memory/working.py** (30 lines)
- Per-query scratchpad.
- `class WorkingMemory`
- `add(key: str, value: Any) -> None`
- `get(key: str) -> Any`
- `get_all() -> dict[str, Any]`
- `clear() -> None`
- `to_context_string() -> str`

### Protocols

**protocols/mcp/client.py**
- `class McpClient`
- `__init__(base_url: str, *, timeout: float = 60.0) -> None`
- `initialize() -> dict[str, Any]`
- `list_tools() -> list[dict[str, Any]]`
- `call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]`

**protocols/a2a/server.py**
- Raw HTTP JSON-RPC A2A server.
- `class A2AServer`
- `__init__(agent: BaseAgent, agent_card_path: str | Path, host: str = "127.0.0.1", port: int = 9001) -> None`
- `serve_forever() -> None`
- `start_background() -> None`
- `shutdown() -> None`
- Handles `GET /.well-known/agent.json`, `POST /a2a`, methods `agent/card`, `tasks/send`.

**protocols/a2a/client.py**
- `class A2AClient`
- `__init__(*, timeout: float = 180.0) -> None`
- `discover(url: str) -> dict[str, Any]`
- `send_task(url: str, message: str) -> dict[str, Any]`
- `agent_card(url: str) -> dict[str, Any]`

**protocols/a2a/discovery.py**
- `class AgentRegistry`
- `register(agent_card: dict[str, Any]) -> None`
- `discover_all() -> list[dict[str, Any]]`
- `find_by_skill(skill_id: str) -> list[dict[str, Any]]`
- `load_from_files(root: str | Path = "agents") -> None`
- Module helpers: `register`, `discover_all`, `find_by_skill`, `load_cards`.

### Agents

**agents/base.py**
- `class BaseAgent(ABC)`
- Abstract: `plan(query: str) -> Any`, `execute(query: str, plan: Any) -> AgentResult`, `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`
- `run(query: str) -> AgentResult`
- `AgentResult`: `analysis`, `sources`, `confidence`.

**agents/market/agent.py** (279 lines)
- `class MarketIntelligenceAgent(BaseAgent)`
- `__init__(mcp_client: McpClient, *, max_retries: int = 2, mcp_server_name: str = "mcp-market-data", semantic_memory: SemanticMemory | None = None, episodic_memory: EpisodicMemory | None = None) -> None`
- `setup() -> None`
- `plan(query: str) -> list[dict[str, Any]]`
- `execute(query: str, plan: list[dict[str, Any]]) -> AgentResult`
- `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`
- `run(query: str) -> AgentResult`
- `_semantic_context(query: str) -> str`
- Uses semantic memory before analysis and logs successful execution to episodic memory.

**agents/market/tools.py**
- `load_tools(client: McpClient) -> list[dict[str, Any]]`
- `tool_names() -> list[str]`
- `format_tools_for_prompt() -> str`
- `extract_text_content(mcp_result: dict[str, Any]) -> str`
- `call_get_quote(client: McpClient, symbol: str) -> dict[str, Any]`

**agents/geopolitical/agent.py**
- `class GeopoliticalRiskAgent(BaseAgent)`
- Uses Granite model knowledge only until geopolitical MCP exists.
- `plan(query: str) -> dict[str, Any]`
- `execute(query: str, plan: dict[str, Any]) -> AgentResult`
- `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`

**agents/supply_chain/agent.py** (128 lines)
- `class SupplyChainAgent(BaseAgent)`
- Uses Granite model knowledge only until supply-chain MCP exists.
- `plan(query: str) -> dict[str, Any]`
- `execute(query: str, plan: dict[str, Any]) -> AgentResult`
- `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`

**agents/synthesis/planner.py**
- `create_execution_plan(query: str, agent_cards: list[dict[str, Any]]) -> dict[str, Any]`
- `agent_key(card: dict[str, Any]) -> str`
- Produces DAG-shaped plan: `{"steps": [{"agent", "task", "depends_on"}], "rationale"}`.

**agents/synthesis/agent.py** (188 lines)
- `class SynthesisAgent`
- `__init__(agent_cards: list[dict[str, Any]], *, a2a_client: A2AClient | None = None, episodic_memory: EpisodicMemory | None = None) -> None`
- `plan(query: str) -> dict[str, Any]`
- `delegate(plan: dict[str, Any]) -> list[dict[str, Any]]`
- `synthesize(query: str, plan: dict[str, Any], agent_results: list[dict[str, Any]]) -> dict[str, Any]`
- `run(query: str) -> dict[str, Any]`
- Queries episodic memory for similar briefings and logs new briefing records.

### Orchestration

**orchestration/state.py**
- `class SynthesisState(TypedDict, total=False)`
- Fields: `messages`, `query`, `agent_cards`, `plan`, `agent_results`, `sources`, `combined_analysis`, `confidence`, `briefing`.
- Reducers: `add_messages`, `merge_agent_results`, `merge_sources`.

**orchestration/graph.py**
- `build_synthesis_graph(agent: SynthesisAgent)`
- LangGraph DAG: `START -> plan -> delegate_to_agents -> synthesize -> END`.

### Observability

**observability/run_logger.py** (34 lines)
- `save_run(run_data: dict[str, Any]) -> Path`
- Writes `runs/YYYYMMDD_HHMMSS.json`.
- Payload keys: `timestamp`, `query`, `execution_plan`, `agent_results`, `sources`, `confidence`, `final_briefing`, `duration_seconds`, `memory_stats`.

### Examples / Scripts

**examples/memory_demo.py** (71 lines)
- `main() -> None`
- Proves semantic, episodic, and working memory independently.

**examples/synthesis_demo.py** (164 lines)
- Starts A2A servers on `9001`, `9002`, `9003`.
- Runs LangGraph synthesis flow.
- Saves JSON run artifact and SQLite briefing record.

Other demos:
- `scripts/verify_ollama.py`
- `examples/langgraph_hello.py`
- `examples/beeai_hello.py`
- `examples/market_agent_demo.py`
- `examples/a2a_demo.py`

### Config

**pyproject.toml**
- Packages: `services`, `examples`, `scripts`, `protocols`, `agents`, `orchestration`, `memory`, `observability`.
- Dependencies include: `langgraph`, `langchain-ollama`, `beeai-framework`, `a2a-sdk`, `mcp`, `httpx`, `chromadb`, `sqlmodel`, `python-dotenv`.
- Scripts include: `atlas-memory-demo`, `atlas-synthesis-demo`.

**.env.example**
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_CHAT_MODEL=ibm/granite4.1:8b`
- `LLM_CHAT_MODEL_NAME=ollama:ibm/granite4.1:8b`
- `OLLAMA_EMBED_MODEL=granite-embedding:278m`

**.gitignore**
- Ignores `.venv/`, `rust/target/`, `data/chroma/`, `data/sqlite/`, `runs/`, `*.db`.

---

## Phase Changelog

### Phase 0 — Environment Setup
- Python venv, Ollama + Granite, LangGraph and BeeAI hello worlds.

### Phase 1A — Rust ollama-check
- Rust workspace and `ollama-check` binary.

### Phase 1B — Rust MCP Market Data Server
- Rust Axum MCP server on `:8001`.
- Python MCP client.
- Yahoo quote parsing with volume baselines.

### Phase 2 — Market Intelligence Agent
- `BaseAgent` plan/execute/reflect loop.
- Market Agent uses MCP and Granite.
- ADR-002 reflection loop depth.

### Phase 3 — A2A Protocol Layer
- Agent Cards.
- A2A server/client/discovery.
- A2A demo.
- ADR-003 HTTP JSON-RPC transport.

### Phase 4 — Multi-agent Coordination
- Geopolitical and Supply Chain agents.
- Synthesis Agent and planner.
- LangGraph orchestration graph.
- Synthesis demo.
- ADR-004 plan object schema.

### Phase 5 — Three-tier Memory Architecture
- Created `services/embeddings.py`.
- Created `memory/semantic.py`, `memory/episodic.py`, `memory/working.py`.
- Created `examples/memory_demo.py`.
- Integrated semantic context and episodic execution logging into `agents/market/agent.py`.
- Integrated episodic retrieval and briefing logging into `agents/synthesis/agent.py`.
- Updated `examples/synthesis_demo.py` to save JSON and SQLite records plus memory stats.
- Updated `observability/run_logger.py` to include `memory_stats`.
- Updated `.env.example` with `OLLAMA_EMBED_MODEL=granite-embedding:278m`.
- ADR-005 episodic memory schema design.

---

## Dependencies Between Files

```text
examples/synthesis_demo.py
  -> protocols/a2a/server.py
  -> agents/market/agent.py
    -> memory/semantic.py
      -> services/embeddings.py -> Ollama /api/embed
    -> memory/episodic.py
    -> protocols/mcp/client.py -> Rust MCP server :8001
    -> services/llm.py -> Ollama / Granite
  -> agents/geopolitical/agent.py -> services/llm.py
  -> agents/supply_chain/agent.py -> services/llm.py
  -> agents/synthesis/agent.py
    -> agents/synthesis/planner.py -> services/llm.py
    -> protocols/a2a/client.py
    -> memory/episodic.py
  -> orchestration/graph.py
    -> orchestration/state.py
  -> observability/run_logger.py

examples/memory_demo.py
  -> memory/semantic.py -> services/embeddings.py -> Ollama /api/embed
  -> memory/episodic.py -> SQLite data/sqlite/atlas_episodic.db
  -> memory/working.py
```

---

## Ports

| Port | Service | Status |
|------|---------|--------|
| 11434 | Ollama | Required for Granite chat and embeddings |
| 8001 | Rust `mcp-market-data` | Required for Market Agent |
| 9001 | A2A Market Agent | Started by demos |
| 9002 | A2A Geopolitical Agent | Started by demos |
| 9003 | A2A Supply Chain Agent | Started by demos |

No new ports were added in Phase 5.

---

## What's Stubbed / Not Yet Built

- `agents/research/` — empty package only.
- `agents/guardian/` — empty package only.
- `ingestion/` — empty package only.
- `ui/` — empty package only.
- `cli/` — empty package only.
- Geopolitical live data MCP server not built; agent uses model knowledge.
- Supply-chain live data MCP server not built; agent uses model knowledge.
- All Rust MCP servers except `mcp-market-data` are not built.
- Observability is minimal: JSON run logging exists, OpenTelemetry spans are not wired yet.

`memory/` is no longer a stub as of Phase 5.