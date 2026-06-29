# CLAUDE.md — Code Context for Claude

> **Project Complete (Phase 16).** All 16 phases implemented. Interview docs in `docs/`. Security: `docs/SECURITY.md`. Verification: `docs/VERIFICATION.md`. Demo: `atlas-taiwan-demo`.

This file is maintained by Cursor after each phase. Claude reads it to understand the codebase without re-reading every file.

Last updated: Phase 16.1 (2026-06-28)

---

## Codebase Metrics

| Metric | Value |
|--------|-------|
| Commits | 23 |
| Total files | 150 |
| Rust LOC | 960 |
| Python LOC | 5,939 |
| Phases complete | 0, 1A, 1B, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 |

---

## Architecture Summary

```text
User (Typer CLI `atlas` / Carbon web UI via `api/` + `web/`)
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
          -> Semantic Memory seed GDELT context when ingested (memory/semantic.py)
          -> Granite analysis with explicit live-data limitation disclosure
        -> Supply Chain Agent :9003 (agents/supply_chain/agent.py)
          -> MCP client -> Rust MCP server :8003 (rust/mcp-trade/) -> UN Comtrade API
          -> Semantic Memory cache (`source=comtrade_live`) when live fetch succeeds
          -> Resilient setup: continues with cache/model path if :8003 unavailable at startup
        -> Research & Filing Agent :9004 (agents/research/agent.py)
          -> Semantic Memory ingest for filing text (memory/semantic.py)
          -> MCP client (protocols/mcp/client.py)
            -> Rust MCP server :8002 (rust/mcp-edgar/)
              -> SEC EDGAR submissions, Archives, full-text search APIs
          -> Granite via Ollama (services/llm.py)
      -> Synthesis Agent queries Episodic Memory for similar briefings
      -> Granite synthesizes unified briefing
      -> Guardian Agent validates grounding and confidence (agents/guardian/agent.py)
        -> If LOW confidence and guardian_retries <= 1, route back to synthesize
        -> Otherwise attach guardian_verdict and continue
      -> Run Logger writes runs/YYYYMMDD_HHMMSS.json (with trace_id)
      -> Episodic Memory writes BriefingRecord (trace_id when tracing active)
      -> OpenTelemetry spans (observability/tracing.py)
        -> graph nodes, agent plan/execute/reflect, llm.chat, mcp.call_tool, a2a.send_task, guardian.validate
        -> exported to console, data/traces/*.json, or Jaeger OTLP (optional)

Scheduled briefing flow:
  APScheduler (services/scheduler.py)
    -> BriefingEngine (services/briefing.py)
      -> For each watchlist topic:
        -> LangGraph Synthesis workflow (plan -> delegate -> synthesize -> guardian)
      -> briefing templates (services/briefing_templates.py)
      -> Run Logger + Episodic Memory

Real-time alert flow:
  AlertWatcher (services/alert_watch.py)
    -> AlertEngine (services/alerts.py)
      -> MCP market data :8001 and/or MCP EDGAR :8002
      -> Granite evaluates alert condition as JSON
      -> If triggered: quick context note, run log, AlertRecord in episodic memory

Memory tiers:
  Tier 1 Semantic: ChromaDB persistent vectors in data/chroma
    -> Taiwan demo seed via ingestion/seed_loader.py (GDELT, filing excerpt)
    -> Live Comtrade rows cached by Supply Chain Agent (`source=comtrade_live`)
  Tier 2 Episodic: SQLite records in data/sqlite/atlas_episodic.db
  Tier 3 Working: in-context scratchpad (memory/working.py), used by demos/LangGraph state

Taiwan Strait demo (Phase 13) — single scenario exercises all paths:
  ingestion/seed_loader.load_taiwan_scenario()
    -> semantic memory (ChromaDB)
  examples/taiwan_demo.py
    -> alert (seed_alert_context + _evaluate_condition)
    -> LangGraph synthesis (4 A2A agents + Guardian)
    -> BriefingEngine (single topic + delta)
    -> OpenTelemetry trace tree
  Equivalent: atlas query "..." | web Query page at http://127.0.0.1:5173 (after seeding)
  Interview script: docs/DEMO_SCRIPT.md
```

---

## File Map

### Rust — Data Layer

**rust/Cargo.toml** — Workspace root. Members: `ollama-check`, `mcp-common`, `mcp-market-data`, `mcp-edgar`.

**rust/mcp-common/** — Shared MCP security middleware (Phase 15).
- `bind_addr(port) -> SocketAddr` — `ATLAS_BIND_HOST`, default `127.0.0.1`
- `apply_security_layers(router)` — CORS, optional rate limit, optional bearer auth
- `require_bearer_auth` — `ATLAS_MCP_AUTH_TOKEN` middleware
- `require_rate_limit` — per-IP limit via `ATLAS_RATE_LIMIT_RPS`
- `validation` — `validate_symbol`, `validate_ticker`, `validate_cik`, `validate_accession_number`, etc.
- `tls_config()`, `listen_scheme()` — optional HTTPS via `ATLAS_TLS_CERT` / `ATLAS_TLS_KEY`

**rust/ollama-check/src/main.rs**
- Phase 1A health check binary.
- `#[tokio::main] async fn main() -> ExitCode`
- `async fn run() -> Result<(), Box<dyn std::error::Error>>`
- `async fn list_models(client: &reqwest::Client, base_url: &str) -> Result<Vec<String>, Box<dyn std::error::Error>>`
- `async fn generate(client: &reqwest::Client, base_url: &str, prompt: &str) -> Result<String, Box<dyn std::error::Error>>`

**rust/mcp-market-data/src/main.rs**
- Axum server on port `8001`, bind `127.0.0.1` by default (`mcp-common::bind_addr`).
- Routes: `GET /health`, `POST /mcp`. Security layers from `mcp-common`.
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

**rust/mcp-edgar/src/main.rs** (60 lines)
- Axum server on port `8002`.
- Routes: `GET /health`, `POST /mcp`.
- Shared state: `AppState { http: reqwest::Client }`.
- Constant: `SEC_USER_AGENT: &str = "Atlas-MCP/0.1 (atlas-project@example.com)"`.
- `async fn main()`
- `async fn health() -> Json<serde_json::Value>`
- `async fn mcp_endpoint(State(state): State<AppState>, Json(request): Json<JsonRpcRequest>) -> Json<serde_json::Value>`
- Dependencies: `axum`, `reqwest`, `serde_json`, `tower_http`, `crate::mcp`.
- Called by: local process via `cargo run -p mcp-edgar`; Python `McpClient` sends HTTP JSON-RPC to `/mcp`.

**rust/mcp-edgar/src/mcp.rs** (147 lines)
- MCP JSON-RPC 2.0 router for SEC filing tools.
- Methods: `initialize`, `tools/list`, `tools/call`.
- Tools: `company_filings`, `filing_text`, `full_text_search`.
- `pub async fn handle_json_rpc(state: AppState, request: JsonRpcRequest) -> Json<Value>`
- `fn handle_initialize() -> Result<Value, (i32, String)>`
- `fn handle_tools_list() -> Result<Value, (i32, String)>`
- `async fn handle_tools_call(state: &AppState, params: Option<Value>) -> Result<Value, (i32, String)>`
- `fn required_str<'a>(args: &'a Value, key: &str) -> Result<&'a str, (i32, String)>`
- `fn json_rpc_success(id: Value, result: Value) -> Value`
- `fn json_rpc_error(id: Value, code: i32, message: &str) -> Value`
- Dependencies: `crate::edgar::{company_filings, filing_text, full_text_search}`, `crate::AppState`, `axum::Json`, `serde`, `serde_json`.
- Called by: `rust/mcp-edgar/src/main.rs::mcp_endpoint`.

**rust/mcp-edgar/src/edgar.rs** (230 lines)
- SEC EDGAR API client.
- Structs:
  - `FilingSummary { accession_number, filing_date, form_type, primary_document, primary_document_url }`
  - `CompanyTicker { cik_str, ticker, title }`
  - `SubmissionResponse { cik, name, filings }`
  - `SubmissionFilings { recent }`
  - `RecentFilings { accession_number, filing_date, form, primary_document }`
- `pub async fn resolve_ticker(client: &reqwest::Client, ticker: &str) -> Result<String, String>`
- `pub async fn company_filings(client: &reqwest::Client, ticker: Option<&str>, cik: Option<&str>) -> Result<Vec<FilingSummary>, String>`
- `pub async fn filing_text(client: &reqwest::Client, cik: &str, accession_number: &str) -> Result<String, String>`
- `pub async fn full_text_search(client: &reqwest::Client, query: &str, form_type: Option<&str>, date_from: Option<&str>) -> Result<Value, String>`
- `pub fn pad_cik(cik: &str) -> String`
- `async fn sec_get(client: &reqwest::Client, url: &str) -> Result<reqwest::Response, String>`
- `async fn sec_delay()`
- `fn strip_html(input: &str) -> String`
- API dependencies: `https://www.sec.gov/files/company_tickers.json`, `https://data.sec.gov/submissions/CIK##########.json`, `https://www.sec.gov/Archives/edgar/data/...`, `https://efts.sec.gov/LATEST/search-index`.
- EDGAR rules: every request includes `SEC_USER_AGENT`; `sec_delay()` waits 125 ms before calls; `pad_cik()` zero-pads CIKs to 10 digits.
- Called by: `rust/mcp-edgar/src/mcp.rs`.

### Services

**services/llm.py**
- Central Granite/Ollama chat config.
- Constants: `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `BEEAI_MODEL_NAME`.
- `def get_chat_ollama(**kwargs: Any) -> ChatOllama`
- `def chat(prompt: str) -> str` — wrapped in OTel span `llm.chat` with `prompt_length`, `response_length`, `model_name`
- `def ollama_generate(prompt: str, *, model: str | None = None) -> str`
- `def list_models() -> list[str]`

**services/embeddings.py** (52 lines)
- Ollama embedding wrapper for semantic memory.
- Constants: `OLLAMA_EMBED_MODEL`.
- `def embed_texts(texts: list[str]) -> list[list[float]]`
- `def _embed_with_model(texts: list[str], model: str) -> list[list[float]]`
- Calls `POST /api/embed` with `OLLAMA_EMBED_MODEL`, falls back to `OLLAMA_CHAT_MODEL`.

**services/briefing.py** (140 lines)
- Scheduled briefing engine over the full synthesis + Guardian pipeline.
- Constants: `DEFAULT_WATCHLIST`.
- `class BriefingEngine`
- `__init__(synthesis_agent: SynthesisAgent, *, episodic_memory: EpisodicMemory | None = None, guardian: GuardianAgent | None = None, briefing_type: str = "daily") -> None`
- `async def generate_briefing(topics: list[str] | None = None) -> dict[str, Any]`
- `_persist(briefing: dict[str, Any]) -> None`
- Helpers:
  - `_topic_query(topic: str) -> str`
  - `_delta_from_last(topic: str, briefing: dict[str, Any], last: Any | None) -> str`
  - `_overall_risk_level(sections: list[dict[str, Any]]) -> str`
  - `_briefing_text_for_memory(briefing: dict[str, Any]) -> str`
- Dependencies: `agents.synthesis.agent.SynthesisAgent`, `agents.guardian.agent.GuardianAgent`, `memory.episodic.EpisodicMemory`, `observability.run_logger.save_run`, `orchestration.graph.build_synthesis_graph`.
- Called by: `examples/briefing_demo.py`, `examples/scheduler_demo.py`, `services/scheduler.py`.

**services/briefing_templates.py** (51 lines)
- Pure formatting helpers; no LLM calls, no data fetching.
- `format_daily_briefing(briefing: dict[str, Any]) -> str`
- `format_summary_line(briefing: dict[str, Any]) -> str`
- Dependencies: `typing.Any`.
- Called by: `examples/briefing_demo.py`, `services/scheduler.py`.

**services/scheduler.py** (88 lines)
- APScheduler integration for autonomous briefings.
- `class AtlasScheduler`
- `__init__(briefing_engine: BriefingEngine) -> None`
- `start() -> None`
- `schedule_daily_briefing(hour: int = 7, minute: int = 0, topics: list[str] | None = None) -> str`
- `schedule_weekly_briefing(day_of_week: str = "mon", hour: int = 7, topics: list[str] | None = None) -> str`
- `schedule_custom(cron_expression: str, topics: list[str]) -> str`
- `stop() -> None`
- `list_jobs() -> list[dict[str, Any]]`
- `async def _run_briefing_job(briefing_type: str, topics: list[str] | None) -> None`
- `_cron_trigger_from_expression(cron_expression: str) -> CronTrigger`
- Dependencies: `apscheduler.schedulers.asyncio.AsyncIOScheduler`, `apscheduler.triggers.cron.CronTrigger`, `services.briefing.BriefingEngine`, `services.briefing_templates.format_summary_line`.
- Called by: `examples/scheduler_demo.py`.

**services/alerts.py** (205 lines)
- Real-time alert engine over fresh MCP data.
- Type aliases/classes:
  - `Severity = Literal["HIGH", "MEDIUM", "LOW"]`
  - `@dataclass AlertRule`: `id`, `name`, `description`, `watch_topic`, `condition_prompt`, `severity`, `cooldown_seconds`
  - `class AlertResult(TypedDict)`: `rule_id`, `rule_name`, `severity`, `triggered_at`, `summary`, `evidence`, `context`, `sources`, `duration_seconds`
  - `class AlertEngine`
- `AlertEngine.__init__(synthesis_agent: SynthesisAgent | None, episodic_memory: EpisodicMemory, guardian: GuardianAgent | None, mcp_client: McpClient | dict[str, McpClient]) -> None`
- `add_rule(rule: AlertRule) -> None`
- `remove_rule(rule_id: str) -> None`
- `list_rules() -> list[AlertRule]`
- `async check_rule(rule: AlertRule) -> AlertResult | None`
- `async check_all_rules() -> list[AlertResult]`
- `_in_cooldown(rule: AlertRule) -> bool`
- `async _fresh_data_for_rule(rule: AlertRule) -> dict[str, Any]`
- `async _market_move_data(rule: AlertRule) -> dict[str, Any]`
- `async _filing_activity_data(rule: AlertRule) -> dict[str, Any]`
- `_client(key: str) -> McpClient`
- Helpers: `_evaluate_condition(rule, fresh_data)`, `_quick_context(rule, fresh_data, verdict)`, `_extract_mcp_json(raw)`, `_extract_symbols(text)`, `_parse_json_from_llm(text)`.
- Dependencies: `protocols.mcp.client.McpClient`, `services.llm.chat`, `memory.episodic.EpisodicMemory`, `observability.run_logger.save_run`.
- Called by: `examples/alert_demo.py`, `examples/alert_watch_demo.py`, `services/alert_watch.py`.

**services/alert_defaults.py** (30 lines)
- Default alert rule factory.
- `default_alert_rules() -> list[AlertRule]`
- Rules: `major_market_move`, `filing_activity`.
- Dependencies: `services.alerts.AlertRule`.
- Called by: alert demos.

**services/alert_watch.py** (52 lines)
- Async watch loop for repeated alert checks.
- `class AlertWatcher`
- `__init__(alert_engine: AlertEngine, check_interval_seconds: int = 300) -> None`
- `async start() -> None`
- `stop() -> None`
- `_on_alert(alert_result: AlertResult) -> None`
- `format_alert(alert_result: dict[str, Any]) -> str`
- Dependencies: `asyncio`, `services.alerts.AlertEngine`, `services.alerts.AlertResult`.
- Called by: `examples/alert_watch_demo.py`.

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

**memory/episodic.py** (220 lines)
- SQLite + SQLModel episodic memory.
- DB path: `data/sqlite/atlas_episodic.db`.
- Tables:
  - `BriefingRecord`: `id`, `timestamp`, `query`, `briefing_type`, `topics`, `plan`, `agent_results`, `final_briefing`, `confidence`, `sources`, `delta_from_last`, `trace_id`, `duration_seconds`.
  - `AlertRecord`: `id`, `timestamp`, `rule_id`, `rule_name`, `trigger`, `agent_chain`, `assessment`, `severity`, `summary`, `evidence`, `context`, `sources`.
  - `AgentExecution`: `id`, `timestamp`, `agent_name`, `task`, `result`, `confidence`, `duration_seconds`.
- `class EpisodicMemory`
- `__init__(db_path: str = DB_PATH) -> None`
- `init_db() -> None`
- `_migrate_briefing_record() -> None`
- `_migrate_alert_record() -> None`
- `log_briefing(run_data: dict[str, Any]) -> BriefingRecord`
- `log_agent_execution(agent_name: str, task: str, result: dict[str, Any], confidence: str, duration: float | None) -> AgentExecution`
- `log_alert(alert_result: dict[str, Any]) -> AlertRecord`
- `query_briefings(query: str, limit: int = 10) -> list[BriefingRecord]`
- `query_briefings_by_date(start: datetime, end: datetime) -> list[BriefingRecord]`
- `get_confidence_history(topic: str, days: int = 90) -> list[dict[str, Any]]`
- `get_last_briefing(topic: str) -> BriefingRecord | None`
- `briefing_count() -> int`
- Phase 7: `log_briefing()` appends `guardian_verdict` into the existing `agent_results` JSON list as `{"agent": "guardian", "verdict": ...}` instead of adding a new column, avoiding SQLite migration churn during local demos.
- Phase 8: `BriefingRecord` stores scheduled-briefing metadata; `_migrate_briefing_record()` adds new SQLite columns for existing local databases.
- Phase 9: `AlertRecord` stores alert rule metadata, evidence, context, and sources; `_migrate_alert_record()` adds new SQLite columns for existing local databases.

**memory/working.py** (30 lines)
- Per-query scratchpad.
- `class WorkingMemory`
- `add(key: str, value: Any) -> None`
- `get(key: str) -> Any`
- `get_all() -> dict[str, Any]`
- `clear() -> None`
- `to_context_string() -> str`

### Protocols

**protocols/auth.py**
- `mcp_auth_token()`, `a2a_auth_token()` — read optional bearer tokens from env
- `auth_headers(token)`, `bearer_authorized(header, expected)` — client/server helpers
- `tls_verify_enabled()` — respects `ATLAS_TLS_INSECURE`

**protocols/mcp/endpoints.py**
- Single source for MCP bind host, ports (`ATLAS_MCP_*_PORT`), URL helpers, and `MCP_HEALTH_TARGETS`.
- `mcp_market_url()`, `mcp_edgar_url()`, `mcp_trade_url()` — used by CLI status, API config, agents, demos.

**protocols/mcp/client.py**
- `class McpClient`
- `__init__(base_url, *, timeout, auth_token, verify_tls)` — auto `ATLAS_MCP_AUTH_TOKEN`
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
- Property: `agent_name: str` — short label for traces (`market`, `geopolitical`, etc.)
- Abstract: `plan(query: str) -> Any`, `execute(query: str, plan: Any) -> AgentResult`, `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`
- `run(query: str) -> AgentResult` — OTel spans: `agent.run`, `agent.plan`, `agent.execute`, `agent.reflect`
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
- Optional `semantic_memory: SemanticMemory | None` in `__init__`; defaults to `SemanticMemory()`.
- `plan(query: str) -> dict[str, Any]`
- `execute(query: str, plan: dict[str, Any]) -> AgentResult` — queries `_semantic_context()` before Granite analysis
- `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`
- `_semantic_context(query: str) -> tuple[str, list[dict[str, Any]]]` — filters matches with `category=geopolitical` or `source=seed_gdelt`
- Uses Granite model knowledge when no seed context; grounds in semantic memory when Taiwan scenario ingested.

**agents/supply_chain/agent.py**
- `class SupplyChainAgent(BaseAgent)`
- Required `mcp_client: McpClient` (Comtrade on `:8003`); URL from `protocols.mcp.endpoints.mcp_trade_url()`.
- `semantic_memory: SemanticMemory` — live Comtrade cache (`source=comtrade_live`), not seed fixtures.
- `setup() -> None` — loads Comtrade tools; try/except so A2A server starts even when MCP is down.
- `plan()` derives Comtrade params (M49 codes, HS cmdCode, period).
- `execute()` — live MCP fetch → cache to ChromaDB on success; on failure query `comtrade_live` cache; insufficient → LOW with no invented figures.
- `reflect()` — downgrades confidence when `used_cache`; forces LOW on insufficient data.
- **agents/supply_chain/tools.py** — `call_get_trade_data`, `call_get_tariffline`, MCP helpers.

**rust/mcp-trade/** — UN Comtrade MCP server on `:8003`.
- `src/main.rs` — `dotenvy::dotenv()` loads `.env`; reads `ATLAS_COMTRADE_API_KEY`; logs keyed vs preview-only mode.
- `src/mcp.rs` — JSON-RPC tools: `get_trade_data`, `get_tariffline`, `preview_trade`.
- `src/comtrade.rs` — Comtrade API client, 250 ms throttle, preview fallback on missing/rejected key.

**agents/research/agent.py** (214 lines)
- `class ResearchFilingAgent(BaseAgent)`
- SEC filing specialist backed by `mcp-edgar`.
- Constant: `DEFAULT_EDGAR_MCP_URL = "http://localhost:8002"`.
- `__init__(mcp_client: McpClient, *, max_retries: int = 2, semantic_memory: SemanticMemory | None = None) -> None`
- `setup() -> None`
- `plan(query: str) -> dict[str, Any]`
- `execute(query: str, plan: dict[str, Any]) -> AgentResult`
- `reflect(query: str, draft: AgentResult) -> tuple[bool, str, Confidence]`
- `_ingest_filing_text(filing_payload: dict[str, Any], args: dict[str, Any]) -> None`
- Helpers:
  - `_fallback_ticker(query: str) -> str`
  - `_query_needs_filing_text(query: str) -> bool`
  - `_first_periodic_filing(filings: dict[str, Any]) -> dict[str, Any] | None`
  - `_cik_for_ticker(ticker: str | None) -> str | None`
  - `_parse_json(text: str) -> dict[str, Any]`
- Dependencies: `agents.base`, `agents.research.tools`, `memory.semantic.SemanticMemory`, `protocols.mcp.client.McpClient`, `services.llm.chat`.
- Called by: `examples/edgar_demo.py`, `examples/synthesis_demo.py` through `A2AServer`.
- Memory behavior: after fetching 10-K/10-Q/20-F text, stores filing text chunks in ChromaDB semantic memory with metadata `source=sec_edgar`, `accession_number`, `cik`.

**agents/research/tools.py** (54 lines)
- MCP helpers for EDGAR tools.
- Global: `AVAILABLE_TOOLS: list[dict[str, Any]]`.
- `load_tools(client: McpClient) -> list[dict[str, Any]]`
- `format_tools_for_prompt() -> str`
- `extract_text_content(mcp_result: dict[str, Any]) -> str`
- `call_company_filings(client: McpClient, *, ticker: str | None = None, cik: str | None = None) -> dict[str, Any]`
- `call_filing_text(client: McpClient, accession_number: str, cik: str) -> dict[str, Any]`
- `call_full_text_search(client: McpClient, query: str, form_type: str | None = None, date_from: str | None = None) -> dict[str, Any]`
- `_parse_tool_result(raw: dict[str, Any]) -> dict[str, Any]`
- Dependencies: `protocols.mcp.client.McpClient`, `json`.
- Called by: `agents/research/agent.py`, `examples/edgar_demo.py`.

**agents/research/agent_card.json** (27 lines)
- A2A Agent Card.
- URL: `http://localhost:9004`.
- Skills:
  - `filing_summary`
  - `financial_extract`
  - `filing_diff`
- Loaded by: `protocols.a2a.discovery.load_cards("agents")`, `examples/synthesis_demo.py`, `A2AServer`.

**agents/guardian/agent.py** (140 lines)
- Second-pass validator. Does not extend `BaseAgent`.
- Type aliases/classes:
  - `Confidence = Literal["HIGH", "MEDIUM", "LOW"]`
  - `class ClaimCheck(TypedDict)`: `claim`, `grounded`, `source`, `confidence`, `issue`
  - `class GuardianVerdict(TypedDict)`: `passed`, `overall_confidence`, `claim_checks`, `flags`, `summary`
  - `class GuardianAgent`
- `GuardianAgent.validate(query: str, briefing: dict[str, Any], agent_results: list[dict[str, Any]], sources: list[dict[str, Any]]) -> GuardianVerdict`
- `_parse_json_from_llm(text: str) -> dict[str, Any]`
- `_normalize_verdict(parsed: dict[str, Any]) -> GuardianVerdict`
- `_normalize_check(check: dict[str, Any]) -> ClaimCheck`
- `_normalize_confidence(value: Any) -> Confidence`
- `_fallback_verdict(message: str) -> GuardianVerdict`
- Dependencies: `services.llm.chat`, `json`, `re`, `datetime`, `typing`.
- Called by: `orchestration/graph.py::guardian_node`, `examples/guardian_demo.py`.
- Behavior: one Granite call validates claims, grounding, source freshness, speculative language, and per-claim/overall confidence; it flags issues but does not rewrite content.

**agents/guardian/agent_card.json** (22 lines)
- A2A Agent Card for future Guardian endpoint.
- URL: `http://localhost:9005`.
- Skills:
  - `validate`
  - `confidence_score`
- Loaded by: `protocols.a2a.discovery.load_cards("agents")`; filtered out of specialist plans by `agents/synthesis/planner.py`.

**agents/synthesis/planner.py** (129 lines)
- `create_execution_plan(query: str, agent_cards: list[dict[str, Any]]) -> dict[str, Any]`
- `agent_key(card: dict[str, Any]) -> str`
- Produces DAG-shaped plan: `{"steps": [{"agent", "task", "depends_on"}], "rationale"}`.
- Phase 6 routing: `agent_key()` maps Research & Filing Agent to `research`; prompt and fallback include Research for filings, earnings, SEC data, risk factors, annual reports, 10-K/10-Q, and company-specific financial details.
- Phase 7 routing: `agent_key()` maps Guardian Agent to `guardian`; Guardian steps are removed from specialist execution plans because Guardian runs as a graph quality gate.

**agents/synthesis/agent.py** (172 lines)
- `class SynthesisAgent`
- `__init__(agent_cards: list[dict[str, Any]], *, a2a_client: A2AClient | None = None, episodic_memory: EpisodicMemory | None = None) -> None`
- `plan(query: str) -> dict[str, Any]`
- `delegate(plan: dict[str, Any]) -> list[dict[str, Any]]`
- `synthesize(query: str, plan: dict[str, Any], agent_results: list[dict[str, Any]], *, guardian_feedback: dict[str, Any] | None = None) -> dict[str, Any]`
- `run(query: str) -> dict[str, Any]`
- Queries episodic memory for similar briefings and logs new briefing records.
- Uses Guardian feedback on retry to remove unsupported claims and avoid inventing evidence.

### Orchestration

**orchestration/state.py** (34 lines)
- `class SynthesisState(TypedDict, total=False)`
- Fields: `messages`, `query`, `agent_cards`, `plan`, `agent_results`, `sources`, `combined_analysis`, `confidence`, `briefing`, `guardian_verdict`, `guardian_retries`.
- Reducers: `add_messages`, `merge_agent_results`, `merge_sources`.

**orchestration/graph.py**
- `build_synthesis_graph(agent: SynthesisAgent, *, guardian: GuardianAgent | None = None, max_guardian_retries: int = 1)`
- `async def run_synthesis_graph(app: Any, state: SynthesisState) -> SynthesisState` — parent span `synthesis.graph`
- LangGraph DAG: `START -> plan -> delegate_to_agents -> synthesize -> guardian -> END`.
- Each node wrapped in OTel span with attributes: `node_name`, `query`, `plan_step_count`, `agent_count`.
- Conditional retry: `guardian` routes back to `synthesize` once when `guardian_verdict.overall_confidence == "LOW"`.

### Observability

**observability/tracing.py**
- `init_tracing(service_name: str | None = None, export_to: str | None = None) -> TracerProvider`
- `get_tracer(name: str) -> Tracer`
- `get_current_trace_id() -> str | None` — hex trace id for run log linkage
- `get_current_span_id() -> str | None`
- `shutdown_tracing() -> None`
- `traced(name: str | None = None)` — decorator wrapping sync/async functions in spans
- Env: `OTEL_EXPORT_TO` (default `console`), `OTEL_SERVICE_NAME` (default `atlas`)

**observability/exporters.py**
- `create_console_exporter() -> SimpleSpanProcessor` — stdout via `ConsoleSpanExporter`
- `create_file_exporter(path: Path | None = None) -> SimpleSpanProcessor` — JSON to `data/traces/YYYYMMDD_HHMMSS.json`
- `create_jaeger_exporter() -> SimpleSpanProcessor` — OTLP HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` set
- `get_active_trace_file() -> Path | None`
- `FileSpanExporter` — custom exporter writing span arrays to JSON

**observability/trace_reader.py**
- `list_traces(directory: str = "data/traces/") -> list[dict[str, Any]]` — trace file metadata, newest first
- `load_trace(filepath: str) -> dict[str, Any]` — parsed spans + span trees by trace_id
- `format_trace_tree(trace: dict[str, Any], *, trace_id: str | None = None) -> str` — indented tree with timing

**observability/run_logger.py**
- `save_run(run_data: dict[str, Any]) -> Path`
- Writes `runs/YYYYMMDD_HHMMSS.json`.
- Persists all non-null keys from `run_data`; auto-adds `trace_id` from active OTel context when missing.

### CLI

**cli/main.py**
- `app: typer.Typer` — root CLI (`atlas = "cli.main:app"`)
- `agent_runtime()` — context manager: MCP check, background A2A servers, agent card load
- `_collect_status() -> dict[str, Any]` — Ollama/MCP/memory/last activity health
- `_build_alert_engine() -> AlertEngine`
- `@app.command() query(text: str)` — full synthesis pipeline + run log + episodic memory
- `@app.command() briefing(briefing_type: str = "daily", topics: str | None)` — `BriefingEngine.generate_briefing()`
- `@app.command() status()` — system health dashboard
- `@app.command() history(limit: int = 10)` — recent `BriefingRecord` rows
- `@alerts_app.command() check()` — `AlertEngine.check_all_rules()` once
- `@alerts_app.command() watch(interval: int = 300)` — `AlertWatcher` loop until Ctrl+C
- `@alerts_app.command() rules()` — list default alert rules
- `@traces_app.command() list()` — `list_traces()` with query metadata
- `@traces_app.command() show(trace_id: str)` — `format_trace_tree()` for one trace

**cli/formatters.py**
- `format_query_result(briefing: dict, *, trace_id: str | None = None) -> str`
- `format_briefing_output(briefing: dict, *, trace_id: str | None = None) -> str`
- `format_alert(alert: dict) -> str`
- `format_status(status: dict) -> str`
- `format_trace_tree(tree: str) -> str`
- `format_history_row(record: dict) -> str`
- Uses `typer.style` ANSI colors: GREEN=HIGH/pass, YELLOW=MEDIUM, RED=LOW/HIGH severity

### API + Web UI

**api/main.py**
- `create_app(*, production: bool = False) -> FastAPI` — mounts routes, optional static UI from `web/dist`
- `main() -> None` — uvicorn entry via `atlas-api` on `:8787`
- Lifespan boots A2A agents via `api/runtime.py`

**api/runtime.py**
- `_check_prerequisites()` — wraps `cli.main._collect_status()` for API readiness
- `_fetch_agent_cards_status()` — probe `:9001`–`:9004` agent cards
- `boot_agent_runtime()` / `shutdown_agent_servers()` — A2A startup for API lifespan

**api/routes/** — `status`, `query` (SSE), `agents`, `briefings`, `alerts`, `traces`

**web/** — Carbon React dashboard (Query, Briefings, Alerts, Agent Status, Trace Viewer)
- Dev: `cd web && npm run dev` → `http://127.0.0.1:5173` (proxies to API `:8787`)
- Prod: `npm run build` + `ATLAS_API_PRODUCTION=1 atlas-api` → `http://127.0.0.1:8787`

### Examples / Scripts

**examples/_demo_infra.py**
- Internal shared helpers for multi-agent demos (not a standalone demo entry point).
- `async def start_mcp_check(urls, *, timeout_seconds) -> None` — polls MCP `GET /health` before agent startup.
- `async def wait_for_agent_cards(urls, *, timeout_seconds) -> None` — polls A2A agent card endpoints.
- `def start_agent_servers() -> list[A2AServer]` — starts Market, Geopolitical, Supply Chain, and Research A2A servers on `:9001`–`:9004`.
- Constants: `DEFAULT_MCP_URLS`, `DEFAULT_AGENT_CARD_URLS`.
- Called by: `examples/synthesis_demo.py`, `examples/briefing_demo.py`, `examples/scheduler_demo.py`.

**examples/memory_demo.py** (71 lines)
- `main() -> None`
- Proves semantic, episodic, and working memory independently.

**examples/synthesis_demo.py**
- Imports `start_mcp_check`, `start_agent_servers`, `wait_for_agent_cards` from `examples._demo_infra`.
- Runs LangGraph synthesis flow with Guardian validation.
- Saves JSON run artifact and SQLite briefing record.

**examples/edgar_demo.py** (43 lines)
- Standalone Phase 6 demo for EDGAR MCP + Research Agent.
- `async def run() -> None`
- `def main() -> None`
- Connects to `DEFAULT_EDGAR_MCP_URL`, lists EDGAR tools, fetches AAPL filings, fetches one 10-K/10-Q text payload, and runs `ResearchFilingAgent`.
- Dependencies: `agents.research.agent`, `agents.research.tools`, `protocols.mcp.client.McpClient`.

**examples/guardian_demo.py** (39 lines)
- Standalone Phase 7 demo for Guardian validation.
- `def main() -> None`
- Builds a fake briefing with one grounded claim and one fabricated claim, then calls `GuardianAgent.validate()`.
- Dependencies: `agents.guardian.agent.GuardianAgent`, `json`, `sys`.

**examples/briefing_demo.py**
- Immediate Phase 8 briefing generation demo.
- Imports startup helpers from `examples._demo_infra`.
- Builds `BriefingEngine`; runs default watchlist; prints `format_daily_briefing()` and `format_summary_line()`.
- Dependencies: `SynthesisAgent`, `GuardianAgent`, `EpisodicMemory`, `BriefingEngine`, briefing templates.

**examples/scheduler_demo.py**
- Autonomous Phase 8 scheduler demo.
- Imports startup helpers from `examples._demo_infra`.
- Schedules `AtlasScheduler.schedule_custom("*/1 * * * *", ["semiconductor supply chain"])`; runs for 185 seconds; shuts down gracefully.
- Dependencies: `AtlasScheduler`, `BriefingEngine`, `SynthesisAgent`, `GuardianAgent`, `EpisodicMemory`, A2A discovery.

**examples/alert_demo.py** (41 lines)
- Phase 9 single-check alert demo.
- `async def run() -> None`
- `def main() -> None`
- Builds `AlertEngine` with market and EDGAR MCP clients, registers `default_alert_rules()`, runs `check_all_rules()` once, and prints triggered alerts with `format_alert()`.
- Dependencies: `services.alerts.AlertEngine`, `services.alert_defaults.default_alert_rules`, `services.alert_watch.format_alert`, `protocols.mcp.client.McpClient`, `memory.episodic.EpisodicMemory`.

**examples/alert_watch_demo.py** (43 lines)
- Phase 9 real-time watch-loop demo.
- `async def run() -> None`
- `def main() -> None`
- Builds `AlertEngine`, registers 1-2 default rules, starts `AlertWatcher(check_interval_seconds=60)`, runs for 180 seconds, and handles `CancelledError` cleanly.
- Dependencies: `services.alert_watch.AlertWatcher`, `services.alerts.AlertEngine`, `services.alert_defaults.default_alert_rules`, `protocols.mcp.client.McpClient`, `memory.episodic.EpisodicMemory`.

**examples/tracing_demo.py**
- Phase 10 OpenTelemetry tracing demo.
- `async def run() -> None`
- `def main() -> None`
- Calls `init_tracing(export_to="file")`, runs full synthesis pipeline via `run_synthesis_graph()`, saves run log with `trace_id`, prints `format_trace_tree()` and trace file path.
- Dependencies: `examples._demo_infra`, `observability.tracing`, `observability.trace_reader`, `orchestration.graph.run_synthesis_graph`.

**examples/taiwan_demo.py**
- Phase 13 Taiwan Strait end-to-end demo scenario.
- Constants: `DEMO_QUERY`, `BRIEFING_TOPIC = "Taiwan Strait semiconductor risk"`.
- `async def run() -> None` — six steps: seed → alert → synthesis → briefing → trace → summary box.
- `async def _run_alert_demo() -> JsonDict | None` — rule `taiwan_strait_tension`, `seed_alert_context()` + `_evaluate_condition()` with HIGH fallback.
- `def main() -> None`
- Dependencies: `ingestion.seed_loader`, `examples._demo_infra`, `orchestration.graph`, `services.briefing`, `services.alerts`, `observability.tracing`, `observability.trace_reader`, `memory.semantic`, `memory.episodic`.

### Ingestion / Seed Data

**data/seed_data/taiwan_scenario.json**
- Simulated GDELT-style conflict events over 5 days for Taiwan Strait escalation.
- Keys: `scenario_name`, `entities`, `events[]` (`date`, `region`, `gldelt_tone`, `goldstein_scale`, `summary`), `aggregate_metrics` (`risk_level: HIGH`, `peak_tone: -9.1`).

**data/seed_data/tsmc_filing_excerpt.txt**
- Simulated TSMC 20-F risk factor excerpt (geopolitical exposure, cross-strait tensions, diversification).

**data/seed_data/trade_flow_data.json**
- Simulated UN Comtrade semiconductor trade flow, `commodities[]`, `chokepoints[]` (TSMC Hsinchu 90% advanced chips).

**data/sample_scenarios/taiwan_demo_expected_output.md**
- Expected alert, briefing structure, trace tree shape, and timing for interviews.

**ingestion/__init__.py**
- Exports `load_taiwan_scenario`, `seed_alert_context`.

**ingestion/seed_loader.py**
- Constants: `SEED_DIR = Path("data/seed_data")`, `SCENARIO_NAME = "taiwan_strait_escalation"`.
- `def _read_text(path: Path) -> str`
- `def _scenario_documents() -> tuple[list[str], list[JsonDict], list[str]]`
- `def load_taiwan_scenario(*, semantic_memory: SemanticMemory | None = None, persist_dir: str = "data/chroma") -> int` — ingests seed files; metadata `source`, `date`, `category`, `scenario_name`; returns document count.
- `def seed_alert_context() -> JsonDict` — fresh-data-shaped payload for demo alert evaluation.

**docs/DEMO_SCRIPT.md**
- Step-by-step interview walkthrough: prerequisites, scripted demo, CLI/dashboard paths, Q&A, fallbacks.

**docs/ARCHITECTURE.md** — system design overview (~5 min read).
**docs/AGENTS.md** — per-agent responsibility, MCP, reflection, Agent Card skills.
**docs/PROTOCOLS.md** — MCP JSON-RPC and A2A delegation details.
**docs/MEMORY.md** — three-tier memory, SQLite schemas, query examples.
**docs/DATA_SOURCES.md** — MCP servers, external APIs, seed data, agent mappings.
**docs/VERIFICATION.md** — pre-interview checklist, known limitations.

**protocols/mcp/__init__.py** — exports `McpClient`.
**orchestration/__init__.py** — exports `build_synthesis_graph`, `run_synthesis_graph`.

Other demos:
- `scripts/verify_ollama.py`
- `examples/langgraph_hello.py`
- `examples/market_agent_demo.py`
- `examples/a2a_demo.py`

### Config

**pyproject.toml**
- Packages: `services`, `examples`, `scripts`, `protocols`, `agents`, `orchestration`, `memory`, `observability`, `cli`, `ingestion`, `api`.
- Dependencies include: `langgraph`, `langchain-ollama`, `beeai-framework`, `a2a-sdk`, `mcp`, `httpx`, `chromadb`, `sqlmodel`, `python-dotenv`.
- `beeai-framework` is retained because `examples/beeai_hello.py` imports it; Atlas production agents use the custom `BaseAgent` pattern.
- Scripts include: `atlas-memory-demo`, `atlas-synthesis-demo`, `atlas-edgar-demo`, `atlas-guardian-demo`, `atlas-briefing-demo`, `atlas-scheduler-demo`, `atlas-alert-demo`, `atlas-alert-watch-demo`, `atlas-tracing-demo`, `atlas-taiwan-demo`, `atlas`, `atlas-api`.

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
- Python venv, Ollama + Granite, LangGraph hello world, and BeeAI hello-world evaluation.
- BeeAI was evaluated but deferred for production agents; specialist agents use the custom `BaseAgent` `plan -> execute -> reflect` pattern.

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

### Phase 6 — Research & Filing Agent with SEC EDGAR MCP Server
- Created `rust/mcp-edgar/Cargo.toml`.
- Created `rust/mcp-edgar/src/main.rs` with Axum server on `:8002`, `/health`, `/mcp`, and SEC `User-Agent`.
- Created `rust/mcp-edgar/src/mcp.rs` with MCP tools `company_filings`, `filing_text`, `full_text_search`.
- Created `rust/mcp-edgar/src/edgar.rs` with ticker-to-CIK resolution, CIK zero-padding, SEC submissions parsing, Archives filing fetch, full-text search, 125 ms SEC rate-limit delay, and HTML stripping.
- Modified `rust/Cargo.toml` to add workspace member `mcp-edgar`.
- Created `agents/research/agent.py` with `ResearchFilingAgent(BaseAgent)`, Granite planning/analysis/reflection, EDGAR MCP calls, and semantic memory ingestion for filing text.
- Created `agents/research/tools.py` with EDGAR MCP helper functions.
- Created `agents/research/agent_card.json` for A2A discovery on `:9004`.
- Modified `agents/research/__init__.py` to export `ResearchFilingAgent`.
- Modified `agents/synthesis/planner.py` to include Research for SEC filings, earnings, risk factors, annual reports, and company-specific financial details.
- Modified `examples/synthesis_demo.py` to start Research A2A server on `:9004` and require EDGAR MCP on `:8002`.
- Created `examples/edgar_demo.py` standalone EDGAR MCP + Research Agent demo.
- Modified `pyproject.toml` to add `atlas-edgar-demo`.
- Verification: `cargo check -p mcp-edgar`, Ruff check, `examples/edgar_demo.py`, and full four-agent `examples/synthesis_demo.py` all completed successfully.

### Phase 7 — Guardian Agent
- Created `agents/guardian/agent.py` with `GuardianAgent`, `GuardianVerdict`, `ClaimCheck`, one-call Granite validation, JSON parsing, verdict normalization, and malformed-JSON fallback.
- Created `agents/guardian/agent_card.json` for future Guardian A2A endpoint on `:9005`.
- Modified `agents/guardian/__init__.py` to export Guardian types/classes.
- Created `examples/guardian_demo.py` with one grounded claim and one fabricated claim.
- Modified `orchestration/graph.py` to run `guardian` after `synthesize` and route back to `synthesize` once on `LOW` confidence.
- Modified `orchestration/state.py` to add `guardian_verdict` and `guardian_retries`.
- Modified `agents/synthesis/agent.py` to accept `guardian_feedback` during retry.
- Modified `agents/synthesis/planner.py` to filter Guardian out of specialist execution plans.
- Modified `examples/synthesis_demo.py` to print Guardian claim checks, flags, pass/fail status, and save Guardian verdicts.
- Modified `observability/run_logger.py` to persist `guardian_verdict`.
- Modified `memory/episodic.py` to store Guardian verdicts inside the existing `agent_results` JSON payload.
- Modified `pyproject.toml` to add `atlas-guardian-demo`.
- Added ADR-007 in `docs/DEVLOG.md` for confidence calibration, Guardian separation of concerns, and retry policy.
- Verification: Ruff check, `examples/guardian_demo.py`, and full Guardian-enabled `examples/synthesis_demo.py` completed successfully.

### Phase 8 — Scheduled Briefings
- Created `services/briefing.py` with `BriefingEngine.generate_briefing()` over the full LangGraph + A2A + Guardian pipeline.
- Created `services/briefing_templates.py` with pure `format_daily_briefing()` and `format_summary_line()` helpers.
- Created `services/scheduler.py` with `AtlasScheduler` over APScheduler `AsyncIOScheduler`.
- Created `examples/briefing_demo.py` for one immediate default-watchlist briefing.
- Created `examples/scheduler_demo.py` for an autonomous 60-second cadence scheduler demo.
- Modified `memory/episodic.py` to add scheduled-briefing metadata, SQLite migration helper, and `get_last_briefing(topic)`.
- Modified `observability/run_logger.py` to persist scheduled-briefing metadata and per-topic summaries.
- Modified `pyproject.toml` to add `atlas-briefing-demo` and `atlas-scheduler-demo`.
- Verification: Ruff check, formatting smoke test, and import/memory smoke test completed successfully.

### Phase 9 — Real-time Monitoring and Alerts
- Created `services/alerts.py` with `AlertRule`, `AlertResult`, `AlertEngine`, MCP fresh-data checks, Granite JSON alert evaluation, cooldown handling, alert persistence, and run logging.
- Created `services/alert_defaults.py` with `major_market_move` and `filing_activity` rules.
- Created `services/alert_watch.py` with `AlertWatcher` async loop and `format_alert()`.
- Created `examples/alert_demo.py` for one-shot default rule checks.
- Created `examples/alert_watch_demo.py` for a 60-second interval watch loop over 3 minutes.
- Modified `memory/episodic.py` with expanded `AlertRecord`, `_migrate_alert_record()`, and `log_alert(alert_result)`.
- Modified `observability/run_logger.py` to include alert metadata.
- Modified `pyproject.toml` to add `atlas-alert-demo` and `atlas-alert-watch-demo`.
- Verification: Ruff check and Phase 9 import smoke test completed successfully.

### Phase 9.1 — Cleanup refactor
- Created `examples/_demo_infra.py` with shared `start_agent_servers()`, `wait_for_agent_cards()`, and `start_mcp_check()` helpers.
- Modified `examples/synthesis_demo.py`, `examples/briefing_demo.py`, and `examples/scheduler_demo.py` to import from `_demo_infra` instead of duplicating startup boilerplate.
- Simplified `observability/run_logger.py` to write all non-null `run_data` fields without a hardcoded schema.
- Updated `README.md` to reflect Phases 0–9 as complete.

### Phase 10 — Full OpenTelemetry Observability
- Created `observability/tracing.py` with `init_tracing()`, `get_tracer()`, `get_current_trace_id()`, `traced()`, and `shutdown_tracing()`.
- Created `observability/exporters.py` with console, file (`data/traces/`), and optional Jaeger OTLP exporters.
- Created `observability/trace_reader.py` with `list_traces()`, `load_trace()`, and `format_trace_tree()`.
- Created `examples/tracing_demo.py` for file-based trace export and printed execution tree.
- Modified `orchestration/graph.py` — OTel spans on graph nodes; added `run_synthesis_graph()` parent span.
- Modified `agents/base.py` — spans on `agent.run`, `plan`, `execute`, `reflect` with agent/attempt/confidence attributes.
- Modified `services/llm.py` — span on `chat()` with prompt/response length and model name.
- Modified `protocols/mcp/client.py` — span on `call_tool()`.
- Modified `protocols/a2a/client.py` — span on `send_task()`.
- Modified `agents/guardian/agent.py` — span on `validate()` with claim counts.
- Modified `services/briefing.py` — parent/topic spans; uses `run_synthesis_graph()`.
- Modified `services/alerts.py` — span per `check_rule()`.
- Modified `observability/run_logger.py` — adds `trace_id` linking run JSON to OTel trace.
- Modified `memory/episodic.py` — `BriefingRecord.trace_id` populated from run data (field existed; now wired).
- Modified `pyproject.toml` — adds `opentelemetry-exporter-otlp-proto-http` and `atlas-tracing-demo`.
- Modified `.gitignore` — ignores `data/traces/`.
- Added ADR-010 in `docs/DEVLOG.md` for trace storage and retention policy.
- Verification: Ruff check and tracing module smoke test completed successfully.

### Phase 11 — Typer CLI Interface
- Created `cli/main.py` with Typer commands: `query`, `briefing`, `status`, `history`, `alerts check|watch|rules`, `traces list|show`.
- Created `cli/formatters.py` with ANSI-colored terminal formatters.
- Modified `pyproject.toml` — adds `atlas = "cli.main:app"` and `cli` wheel package.
- Modified `README.md` — CLI usage section and Phase 11 status.
- Added Phase 11 entry in `docs/DEVLOG.md`.
- Verification: Ruff check, `atlas --help`, and `atlas status` smoke test completed successfully.

### Phase 12 — Streamlit Web Dashboard
- Created `ui/streamlit_app.py` with sidebar navigation, system status, and `run_dashboard()`.
- Created `ui/runtime.py` with prerequisites checks, session-scoped A2A auto-start, and status helpers.
- Created `ui/components.py` with confidence/guardian/severity badges, agent cards, source lists, span tree renderer.
- Created `ui/pages/query.py`, `briefings.py`, `alerts.py`, `agent_status.py`, `trace_viewer.py`.
- Modified `pyproject.toml` — adds `atlas-dashboard` and `ui` package.
- Modified `README.md` — dashboard section and Phase 12 status.
- Added Phase 12 entry in `docs/DEVLOG.md`.
- Verification: Ruff check and UI import smoke test completed successfully.

### Phase 13 — Taiwan Strait Demo Scenario
- Created `data/seed_data/taiwan_scenario.json`, `tsmc_filing_excerpt.txt`, `trade_flow_data.json` — simulated GDELT, filing, and trade-flow seed data.
- Created `ingestion/seed_loader.py` with `load_taiwan_scenario()` and `seed_alert_context()`.
- Created `examples/taiwan_demo.py` — six-step end-to-end demo (seed, alert, synthesis, briefing, trace, summary).
- Created `data/sample_scenarios/taiwan_demo_expected_output.md` and `docs/DEMO_SCRIPT.md`.
- Modified `agents/geopolitical/agent.py` — optional semantic memory; `_semantic_context()` in `execute()`.
- Modified `agents/supply_chain/agent.py` — live Comtrade MCP + ChromaDB cache (Phase 16).
- Modified `pyproject.toml` — adds `ingestion` package and `atlas-taiwan-demo` script.
- Modified `README.md` and `docs/DEVLOG.md` — Phase 13 status and demo instructions.
- Verification: Ruff check and import smoke test completed successfully.

### Phase 14 — Polish and Presentation
- Ran `ruff check --fix` + `ruff format` across entire Python codebase (46 files reformatted).
- Ran `cargo clippy --all` and `cargo fmt --all` on Rust workspace — no clippy warnings.
- Created `docs/ARCHITECTURE.md`, `docs/AGENTS.md`, `docs/PROTOCOLS.md`, `docs/MEMORY.md`, `docs/DATA_SOURCES.md`, `docs/VERIFICATION.md`.
- Modified `README.md` — Quick Start, What Makes This Different, Project Structure, Phase 14 complete.
- Modified `protocols/mcp/__init__.py` — exports `McpClient`.
- Modified `orchestration/__init__.py` — exports `run_synthesis_graph`.
- Added ADR-011 in `docs/DEVLOG.md` for documentation structure.
- Verification: full ruff pass, clippy pass, import smoke tests.

### Phase 14.1 — Streamlit UI fixes
- Renamed `ui/pages/` → `ui/views/` to prevent Streamlit auto page discovery (duplicate sidebar tabs).
- Fixed `ui/streamlit_app.py` recursive launch: `run_dashboard()` only when Streamlit script context is active (`get_script_run_ctx()`); `main()` subprocess only.
- Added `.streamlit/config.toml` with `headless` and `showSidebarNavigation = false`.
- Added `ui/styles.py` design system; polished `ui/components.py` (pills, metric cards, HTML trace tree).
- Cached `get_status()` (10s), `fetch_agent_cards_status()` (15s), synthesis stack and alert engine via `@st.cache_*`.
- Updated all views: tabbed query results, status grid, alert cards, HTML trace viewer, briefing callouts.

### Phase 15 — Production security hardening
- Created `rust/mcp-common/` — bind `127.0.0.1`, bearer auth, rate limit, CORS, TLS, input validation.
- MCP servers default localhost; optional `ATLAS_MCP_AUTH_TOKEN`, `ATLAS_RATE_LIMIT_RPS`, `ATLAS_TLS_*`.
- Created `protocols/auth.py`; updated `McpClient`, `A2AClient`, `A2AServer` for bearer tokens.
- API bind `127.0.0.1`; `docs/SECURITY.md`; ADR-012 in `docs/DEVLOG.md`.

### Post-Phase 15 — Carbon web UI replaces Streamlit
- Removed `ui/` Streamlit package, `streamlit` dependency, and `atlas-dashboard` entry point.
- Graphical interface is now Carbon React (`web/`) + FastAPI (`api/`, `atlas-api`).

### Phase 16 — UN Comtrade MCP + live SupplyChainAgent
- Created `rust/mcp-trade/` — Axum MCP on `:8003`, dotenvy loads `ATLAS_COMTRADE_API_KEY`, Comtrade API client with preview fallback.
- Added Comtrade validators to `rust/mcp-common/src/validation.rs`.
- Created `agents/supply_chain/tools.py`; rewrote `agents/supply_chain/agent.py` for live-first Comtrade + ChromaDB cache.
- Removed trade-flow seed ingestion from `ingestion/seed_loader.py` (GDELT seed untouched).
- Updated `examples/_demo_infra.py` — `:8003` health check, SupplyChainAgent wired to McpClient.
- Updated docs: README, DATA_SOURCES, MEMORY, ADR-013 in DEVLOG.

### Phase 16.1 — MCP endpoint wiring
- Created `protocols/mcp/endpoints.py` — shared MCP URLs, ports, `MCP_HEALTH_TARGETS`.
- Wired `cli/main.py` `_collect_status()`, `api/config.py`, `api/runtime.py`, agent default URLs, `examples/_demo_infra.py`.
- Resilient `SupplyChainAgent.setup()` — no crash when `:8003` is down at A2A startup.
- Docs sweep: PRD, VERIFICATION, SECURITY, PROTOCOLS, AGENTS, demo prerequisites.

---

## Dependencies Between Files

```text
examples/synthesis_demo.py
  -> examples/_demo_infra.py
    -> protocols/a2a/server.py
    -> agents/market/agent.py -> protocols/mcp/client.py -> Rust MCP server :8001
    -> agents/geopolitical/agent.py -> services/llm.py
    -> agents/supply_chain/agent.py -> protocols/mcp/client.py -> Rust MCP server :8003
    -> agents/research/agent.py -> protocols/mcp/client.py -> Rust MCP server :8002
  -> agents/synthesis/agent.py
    -> agents/synthesis/planner.py -> services/llm.py
    -> protocols/a2a/client.py
    -> memory/episodic.py
  -> orchestration/graph.py
    -> orchestration/state.py
    -> agents/guardian/agent.py -> services/llm.py
  -> memory/semantic.py -> services/embeddings.py -> Ollama /api/embed
  -> memory/episodic.py
  -> observability/run_logger.py

examples/memory_demo.py
  -> memory/semantic.py -> services/embeddings.py -> Ollama /api/embed
  -> memory/episodic.py -> SQLite data/sqlite/atlas_episodic.db
  -> memory/working.py

examples/edgar_demo.py
  -> agents/research/agent.py
  -> agents/research/tools.py
  -> protocols/mcp/client.py -> Rust MCP server :8002
    -> rust/mcp-edgar/src/mcp.rs
      -> rust/mcp-edgar/src/edgar.rs -> SEC EDGAR APIs

examples/guardian_demo.py
  -> agents/guardian/agent.py -> services/llm.py

examples/briefing_demo.py
  -> examples/_demo_infra.py
  -> services/briefing.py
    -> orchestration/graph.py
      -> agents/synthesis/agent.py
      -> agents/guardian/agent.py
    -> memory/episodic.py
    -> observability/run_logger.py
  -> services/briefing_templates.py

examples/scheduler_demo.py
  -> examples/_demo_infra.py
  -> services/scheduler.py
    -> services/briefing.py
      -> LangGraph synthesis + Guardian pipeline

examples/alert_demo.py
  -> services/alerts.py
    -> protocols/mcp/client.py -> Rust MCP server :8001 / :8002
    -> services/llm.py -> Ollama / Granite
    -> memory/episodic.py -> AlertRecord
    -> observability/run_logger.py

examples/alert_watch_demo.py
  -> services/alert_watch.py
    -> services/alerts.py
      -> observability/tracing.py (alerts.check_rule span)
      -> MCP tools + Granite condition evaluation

examples/tracing_demo.py
  -> observability/tracing.py (init_tracing export_to=file)
  -> examples/_demo_infra.py
  -> orchestration/graph.py (run_synthesis_graph)
  -> observability/trace_reader.py (format_trace_tree)
  -> observability/run_logger.py (trace_id linkage)
  -> memory/episodic.py

cli/main.py
  -> cli/formatters.py
  -> examples/_demo_infra.py (query, briefing: auto-start A2A)
  -> orchestration/graph.py (query: run_synthesis_graph)
  -> services/briefing.py (briefing command)
  -> services/alerts.py + services/alert_defaults.py + services/alert_watch.py (alerts commands)
  -> memory/episodic.py (history, status)
  -> memory/semantic.py (status)
  -> observability/trace_reader.py (traces commands)
  -> observability/run_logger.py + observability/tracing.py (query)

api/main.py
  -> api/runtime.py -> cli/main.py + examples/_demo_infra.py
  -> api/routes/query.py -> orchestration/graph.py, observability/run_logger.py, memory/episodic.py
  -> api/routes/briefings.py -> services/briefing.py, memory/episodic.py
  -> api/routes/alerts.py -> services/alerts.py, services/alert_defaults.py
  -> api/routes/status.py -> cli/main._collect_status()
  -> api/routes/traces.py -> observability/trace_reader.py
  -> web/ (Carbon React UI, dev proxy to :8787)

ingestion/seed_loader.py
  -> memory/semantic.py -> services/embeddings.py -> Ollama /api/embed
  -> data/seed_data/taiwan_scenario.json
  -> data/seed_data/tsmc_filing_excerpt.txt
  -> data/seed_data/trade_flow_data.json

examples/taiwan_demo.py
  -> ingestion/seed_loader.py (load_taiwan_scenario, seed_alert_context)
  -> examples/_demo_infra.py (MCP check, A2A servers)
  -> services/alerts.py (_evaluate_condition for demo alert)
  -> orchestration/graph.py (run_synthesis_graph)
  -> agents/geopolitical/agent.py -> memory/semantic.py (seed GDELT)
  -> agents/supply_chain/agent.py -> protocols/mcp/client.py -> rust/mcp-trade :8003
  -> agents/supply_chain/agent.py -> memory/semantic.py (comtrade_live cache)
  -> agents/market/agent.py -> MCP :8001
  -> agents/research/agent.py -> MCP :8002
  -> services/briefing.py (BriefingEngine)
  -> observability/tracing.py + observability/trace_reader.py
  -> observability/run_logger.py + memory/episodic.py
  -> docs/DEMO_SCRIPT.md (interview walkthrough)
```

---

## Ports

| Port | Service | Status |
|------|---------|--------|
| 11434 | Ollama | Required for Granite chat and embeddings |
| 8001 | Rust `mcp-market-data` | Required for Market Agent |
| 8002 | Rust `mcp-edgar` | Required for Research & Filing Agent |
| 8003 | Rust `mcp-trade` | Required for Supply Chain Agent |
| 9001 | A2A Market Agent | Started by demos |
| 9002 | A2A Geopolitical Agent | Started by demos |
| 9003 | A2A Supply Chain Agent | Started by demos |
| 9004 | A2A Research & Filing Agent | Started by demos |
| 9005 | A2A Guardian Agent | Agent Card reserved; validation currently runs in graph |
| 8787 | Atlas API (`atlas-api`) | FastAPI + optional production static UI |
| 5173 | Vite dev UI | `cd web && npm run dev` |

---

## What's Stubbed / Not Yet Built

- Geopolitical live GDELT MCP server not built; agent uses semantic memory seed + model knowledge.
- Rust MCP servers built: `mcp-market-data`, `mcp-edgar`, `mcp-trade`; future MCP servers remain unbuilt.

`memory/` is no longer a stub as of Phase 5. `agents/research/` is no longer a stub as of Phase 6. `agents/guardian/` is no longer a stub as of Phase 7. `observability/` is no longer a stub as of Phase 10. `cli/` is no longer a stub as of Phase 11. `api/` + `web/` provide the graphical interface (replacing the Phase 12 Streamlit dashboard). `ingestion/` has `seed_loader.py` as of Phase 13 (Taiwan scenario); full live ingestion pipelines remain unbuilt.