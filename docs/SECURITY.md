# Atlas Security

Production hardening model for the Atlas local-first intelligence platform.

---

## Network exposure (as-built defaults)

| Surface | Default bind | LAN reachable? | Notes |
|---------|--------------|----------------|-------|
| MCP market-data `:8001` | `127.0.0.1` | No (default) | `ATLAS_BIND_HOST` overrides |
| MCP edgar `:8002` | `127.0.0.1` | No (default) | Same |
| A2A agents `:9001–9004` | `127.0.0.1` | No | Python `A2AServer` default |
| Ollama `:11434` | `127.0.0.1` | No | Ollama default, not Atlas-controlled |
| Streamlit dashboard | `127.0.0.1` | No | `.streamlit/config.toml` |

Prior to Phase 15, Rust MCP servers bound to `0.0.0.0` and Streamlit used its default bind. Both now default to localhost.

---

## Secrets in flight

- **No API keys** are transmitted between Atlas components today.
- **Yahoo Finance** — no credentials required.
- **SEC EDGAR** — `User-Agent` header only (`Atlas-MCP/0.1 (...)`), no API key.
- **Ollama** — local inference, no cloud API key.

Production auth tokens (`ATLAS_MCP_AUTH_TOKEN`, `ATLAS_A2A_AUTH_TOKEN`) are optional shared secrets for service-to-service calls, not upstream API keys.

---

## Configuration matrix

| Variable | Dev default (unset) | Production |
|----------|---------------------|------------|
| `ATLAS_BIND_HOST` | `127.0.0.1` | `127.0.0.1` (or `0.0.0.0` behind reverse proxy) |
| `ATLAS_MCP_AUTH_TOKEN` | Auth disabled | Shared bearer token on `/health` and `/mcp` |
| `ATLAS_A2A_AUTH_TOKEN` | Auth disabled | Shared bearer token on agent card + `/a2a` |
| `ATLAS_TLS_CERT` / `ATLAS_TLS_KEY` | Plain HTTP | Rust MCP servers serve HTTPS |
| `ATLAS_TLS_INSECURE` | TLS verify on | Set `1` only for local self-signed certs |
| `ATLAS_RATE_LIMIT_RPS` | No limit | Per-IP requests/sec on MCP endpoints |
| `ATLAS_CORS_ORIGINS` | Localhost origins | Comma-separated allowlist |

See [`.env.example`](../.env.example) for commented examples.

---

## What Phase 15 implemented

### Rust MCP layer (`rust/mcp-common/`)

- **Bind** — `bind_addr()` reads `ATLAS_BIND_HOST`, default `127.0.0.1`
- **Auth** — Bearer middleware when `ATLAS_MCP_AUTH_TOKEN` is set (constant-time compare)
- **Rate limit** — Per-IP token bucket when `ATLAS_RATE_LIMIT_RPS` is set (HTTP 429)
- **CORS** — Localhost-only default; `ATLAS_CORS_ORIGINS` for production allowlist
- **TLS** — Optional `rustls` via `ATLAS_TLS_CERT` / `ATLAS_TLS_KEY`
- **Input validation** — Symbol, ticker, CIK, accession number, search query, form type, date filters

### Python protocol layer

- [`protocols/auth.py`](../protocols/auth.py) — central env helpers
- [`protocols/mcp/client.py`](../protocols/mcp/client.py) — auto-attaches MCP bearer token + TLS verify flag
- [`protocols/a2a/client.py`](../protocols/a2a/client.py) — auto-attaches A2A bearer token
- [`protocols/a2a/server.py`](../protocols/a2a/server.py) — rejects unauthorized requests when token configured

### Dashboard

- [`.streamlit/config.toml`](../.streamlit/config.toml) — `server.address = "127.0.0.1"`

---

## TLS strategy

| Component | Native TLS | Recommended production path |
|-----------|------------|----------------------------|
| Rust MCP servers | Yes (`axum-server` + `rustls`) | Native or reverse proxy |
| Python A2A servers | No | TLS termination at Caddy/nginx |
| Streamlit | No | Reverse proxy or SSH tunnel |

Defense in depth: even on localhost, TLS prevents other local processes from sniffing loopback traffic when certificates are configured.

---

## Rate limiting layers

Two separate concerns:

1. **SEC compliance** — `mcp-edgar` enforces 125 ms delay between upstream SEC API calls (regulatory politeness).
2. **MCP endpoint protection** — `ATLAS_RATE_LIMIT_RPS` limits inbound requests per client IP to prevent flooding the local MCP servers.

---

## HTTP vs WebSockets

Atlas uses **HTTP request-response** for MCP and A2A. This is intentional:

- MCP tool calls are single round-trips (quote fetch ~200 ms, Granite inference ~4 s).
- WebSocket connection setup savings (~1–5 ms) are negligible vs GPU inference.
- HTTP is debuggable with `curl`, browser tools, and structured logs.

**Where WebSockets would help in production:**

- Streaming LLM tokens to the UI (Ollama supports `stream: true`)
- Perceived latency reduction for long agent tasks (A2A SSE streaming)

Atlas agents need complete LLM responses before reflection and planning; streaming is a UI-layer enhancement, not an agent-protocol change.

---

## Production checklist

1. Set `ATLAS_BIND_HOST=127.0.0.1` (or place services behind a reverse proxy)
2. Generate strong `ATLAS_MCP_AUTH_TOKEN` and `ATLAS_A2A_AUTH_TOKEN`
3. Configure TLS certificates or reverse proxy termination
4. Set `ATLAS_RATE_LIMIT_RPS` (e.g. `10`)
5. Restrict `ATLAS_CORS_ORIGINS` to known frontends
6. Never commit `.env` with real tokens

---

## Related docs

- [PROTOCOLS.md](PROTOCOLS.md) — wire protocol details
- [ARCHITECTURE.md](ARCHITECTURE.md) — system overview
- [VERIFICATION.md](VERIFICATION.md) — security smoke tests
