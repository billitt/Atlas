# Atlas Protocols

How MCP and A2A are implemented in Atlas, and how they work together.

---

## Overview

| Protocol | Direction | Purpose | Implementation |
|----------|-----------|---------|----------------|
| **MCP** | Agent → data tools | Fetch live quotes, SEC filings | Rust Axum servers, Python `McpClient` |
| **A2A** | Agent → agent | Delegate specialist tasks | Python `A2AServer` / `A2AClient` |

**MCP = agent↔data.** Each specialist calls Rust MCP servers for external APIs.  
**A2A = agent↔agent.** Synthesis delegates work to specialists without embedding their logic.

---

## MCP Implementation

### Transport

- **Endpoint:** `POST /health` (health check), `POST /mcp` (JSON-RPC)
- **Format:** JSON-RPC 2.0
- **Client:** `protocols/mcp/client.py` — `McpClient(base_url)`

### Client API

```python
client = McpClient("http://localhost:8001")
client.initialize()           # → server capabilities
client.list_tools()           # → tool schemas
client.call_tool(name, args)  # → tool result
```

All calls are traced via OpenTelemetry (`mcp.call_tool` spans).

### Server methods (both Rust crates)

| Method | Purpose |
|--------|---------|
| `initialize` | Protocol version, server info, capabilities |
| `tools/list` | Available tools with JSON Schema `inputSchema` |
| `tools/call` | Execute tool by name with arguments |

### mcp-market-data (:8001)

**Tool:** `get_quote`

```json
{
  "name": "get_quote",
  "inputSchema": {
    "type": "object",
    "properties": { "symbol": { "type": "string" } },
    "required": ["symbol"]
  }
}
```

Returns text content block with price, change %, volume vs 5-day average.

### mcp-edgar (:8002)

**Tools:**

| Tool | Arguments | Returns |
|------|-----------|---------|
| `company_filings` | `ticker` or `cik` | Recent filing summaries |
| `filing_text` | `cik`, `accession_number` | Full filing document text |
| `full_text_search` | `query`, optional `form_type`, `date_from` | SEC search index hits |

SEC compliance: every request includes `User-Agent: Atlas-MCP/0.1 (...)` and 125 ms delay between calls.

### mcp-trade (:8003)

**Tools:**

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_trade_data` | `reporterCode`, `period`, optional `partnerCode`, `cmdCode`, `flowCode` | UN Comtrade trade rows |
| `get_tariffline` | Same | Tariff-line granularity rows |
| `preview_trade` | Same | Keyless preview (max 500 records) |

Keyed calls use `ATLAS_COMTRADE_API_KEY`; 250 ms delay between upstream calls. Falls back to preview when key is absent or rejected.

### Security (Phase 15)

Shared middleware in `rust/mcp-common/`:

| Control | Env var | Default |
|---------|---------|---------|
| Bind address | `ATLAS_BIND_HOST` | `127.0.0.1` |
| Bearer auth | `ATLAS_MCP_AUTH_TOKEN` | disabled |
| Rate limit | `ATLAS_RATE_LIMIT_RPS` | disabled |
| CORS | `ATLAS_CORS_ORIGINS` | localhost origins |
| TLS | `ATLAS_TLS_CERT`, `ATLAS_TLS_KEY` | plain HTTP |

Python `McpClient` reads `ATLAS_MCP_AUTH_TOKEN` and sends `Authorization: Bearer …` automatically. Input validation rejects malformed symbols, tickers, CIKs, and accession numbers before upstream calls.

See [SECURITY.md](SECURITY.md) for the full matrix.

### Error handling

JSON-RPC errors use standard codes (`-32600` invalid request, `-32601` method not found, `-32602` invalid params). Tool failures return `isError: true` in MCP content.

---

## A2A Implementation

### Agent Cards

Each specialist publishes a card at `GET /.well-known/agent.json`:

```json
{
  "name": "Market Intelligence Agent",
  "url": "http://localhost:9001",
  "skills": [{ "id": "market_snapshot", "name": "...", "description": "..." }]
}
```

Cards are loaded by `protocols/a2a/discovery.py` from `agents/*/agent_card.json`.

### Transport

- **Discovery:** `GET /.well-known/agent.json`
- **Tasks:** `POST /a2a` with JSON-RPC 2.0

### Client API

```python
client = A2AClient()
card = client.discover("http://localhost:9001")
result = client.send_task("http://localhost:9001", "Analyze TSM exposure...")
```

`send_task` is traced (`a2a.send_task` spans).

When `ATLAS_A2A_AUTH_TOKEN` is set, both `discover` and `send_task` attach bearer headers. `A2AServer` rejects unauthorized requests on agent card and `/a2a` endpoints.

### Server

`A2AServer` wraps a `BaseAgent` instance:

- Handles `agent/card` and `tasks/send`
- Runs `agent.run(message)` and returns analysis + sources + confidence

Demos start four servers on ports 9001–9004 via `examples/_demo_infra.py`.

### Registry

`AgentRegistry` supports:

- `load_from_files("agents")` — load all Agent Cards
- `find_by_skill(skill_id)` — discover agents by capability
- Used by Synthesis planner to build execution DAG

---

## How Protocols Complement Each Other

```text
User query: "TSMC risk if Taiwan tensions escalate"
                    │
                    ▼
            Synthesis Agent
                    │
         A2A tasks/send ─────────────────────────────┐
                    │                                │
    ┌───────────────┼───────────────┐                │
    ▼               ▼               ▼                ▼
 Market         Geopolitical   Supply Chain    Research
    │               │               │                │
 MCP get_quote   Semantic      Semantic         MCP company_filings
    │             memory          memory              │
    ▼               │               │                ▼
 Yahoo API      ChromaDB        ChromaDB          SEC EDGAR
```

- **Synthesis never calls MCP directly** — it delegates to specialists
- **Market and Research use MCP** for live external data
- **Geopolitical and Supply Chain use semantic memory** (seed data today; future MCP)
- **A2A keeps specialists decoupled** — add a new agent by publishing a card and starting a server

---

## Design Rationale (ADR-003)

HTTP JSON-RPC was chosen over gRPC for A2A transport:

- Simple to debug with curl and browser tools
- Aligns with MCP HTTP transport pattern
- Sufficient for local demo and portfolio deployment

Future production could add gRPC or message queues without changing agent logic — only the protocol layer.

---

## Related Docs

- [SECURITY.md](SECURITY.md) — production hardening and network exposure
- [ARCHITECTURE.md](ARCHITECTURE.md) — language boundary and workflows
- [DATA_SOURCES.md](DATA_SOURCES.md) — MCP server details and rate limits
- [AGENTS.md](AGENTS.md) — which agents use which protocols
