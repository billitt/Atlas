# Atlas

Atlas is a local-first global intelligence platform built around protocol-native AI agents. It combines Rust data services, Python agent orchestration, MCP tool access, A2A agent-to-agent delegation, LangGraph workflows, and IBM Granite running locally through Ollama.

The project is designed as a portfolio-grade demonstration of hybrid Rust + Python systems, agentic AI architecture, reflection loops, and open-source/on-prem inference.

See [PRD.md](PRD.md) for the full product plan and [docs/DEVLOG.md](docs/DEVLOG.md) for detailed implementation notes and ADRs.

## Current Status

Phases **0-4 are implemented and demo-verified**.

| Phase | Status | What Works |
|-------|--------|------------|
| 0 | Complete | Python environment, Ollama, Granite, LangGraph, BeeAI hello worlds |
| 1A | Complete | Rust `ollama-check` binary verifies local Ollama + Granite |
| 1B | Complete | Rust MCP market-data server serves Yahoo Finance quotes on port `8001` |
| 2 | Complete | Market Intelligence Agent: query -> plan -> MCP fetch -> analyze -> reflect |
| 3 | Complete | A2A Agent Cards, discovery, HTTP JSON-RPC delegation |
| 4 | Complete | Synthesis Agent coordinates Market, Geopolitical, and Supply Chain agents through LangGraph + A2A |

Future phases begin with Phase 5: memory architecture.

## Architecture Snapshot

```text
User query
  -> LangGraph Synthesis workflow
  -> Synthesis Agent creates execution plan with Granite
  -> A2A delegates tasks to specialist agents
  -> Specialist agents reason with Granite through Ollama
  -> Market Agent calls Rust MCP server for live Yahoo market data
  -> Synthesis Agent merges all outputs into one briefing
```

### Framework Roles

| Layer | Technology | Role |
|-------|------------|------|
| Local LLM runtime | Ollama | Hosts and runs `ibm/granite4.1:8b` |
| LLM | IBM Granite 4.1 8B | Planning, analysis, reflection, synthesis |
| Orchestration | LangGraph | Traceable workflow: plan -> delegate -> synthesize |
| Agent delegation | A2A-style HTTP JSON-RPC | Agent discovery and `tasks/send` delegation |
| Tool/data protocol | MCP-style HTTP JSON-RPC | Market Agent calls Rust tools through `/mcp` |
| Data layer | Rust + Axum | High-performance MCP market-data server |
| Agent layer | Python | Specialist agents, protocol clients, synthesis logic |
| Market data | Yahoo Finance chart API | Live quote and volume baseline data |

## Runtime Services

| Service | Port | Started By | Purpose |
|---------|------|------------|---------|
| Ollama | `11434` | Ollama app / CLI | Runs Granite locally |
| Rust MCP market data | `8001` | `cargo run -p mcp-market-data` | Serves `get_quote` tool |
| Market A2A Agent | `9001` | Demo scripts | Market Intelligence Agent endpoint |
| Geopolitical A2A Agent | `9002` | Demo scripts | Model-knowledge geopolitical analysis |
| Supply Chain A2A Agent | `9003` | Demo scripts | Model-knowledge supply-chain analysis |

## Setup

### Prerequisites

- Python 3.11+
- Rust stable toolchain
- [Ollama](https://ollama.com/download)
- NVIDIA GPU recommended for Granite 4.1 8B Q4 (~5.3 GB VRAM)

### Pull Granite

```powershell
ollama pull ibm/granite4.1:8b
```

If `ollama` is not on PATH on Windows:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull ibm/granite4.1:8b
```

### Install Python Package

```powershell
cd c:\Users\ezzao\OneDrive\Documents\atlas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Verify Ollama + Granite

```powershell
python -m scripts.verify_ollama
python -m examples.langgraph_hello
python -m examples.beeai_hello
```

Entry points after installation:

```powershell
atlas-verify-ollama
atlas-langgraph-hello
atlas-beeai-hello
```

## Phase-by-Phase Implementation

### Phase 0 - Environment Setup

Verified the Python environment and local LLM stack:

- Ollama installed and serving locally
- IBM Granite 4.1 8B pulled into Ollama
- LangGraph hello world
- BeeAI hello world
- Shared LLM helper in `services/llm.py`

Key files:

- `services/llm.py`
- `scripts/verify_ollama.py`
- `examples/langgraph_hello.py`
- `examples/beeai_hello.py`

### Phase 1A - Rust Ollama Health Check

Added a Rust workspace and binary that verifies Ollama + Granite from Rust.

Key files:

- `rust/Cargo.toml`
- `rust/ollama-check/Cargo.toml`
- `rust/ollama-check/src/main.rs`

Run:

```powershell
cd c:\Users\ezzao\OneDrive\Documents\atlas\rust
cargo run -p ollama-check
```

### Phase 1B - Rust MCP Market Data Server

Implemented the first Rust MCP-style server:

- `GET /health`
- `POST /mcp`
- JSON-RPC methods: `initialize`, `tools/list`, `tools/call`
- Tool: `get_quote`
- Yahoo Finance quote data
- Volume grounding fields:
  - `previous_day_volume`
  - `average_volume_5d`
  - `volume_vs_average_percent`

Key files:

- `rust/mcp-market-data/src/main.rs`
- `rust/mcp-market-data/src/mcp.rs`
- `rust/mcp-market-data/src/yahoo.rs`
- `protocols/mcp/client.py`

Run the server:

```powershell
cd c:\Users\ezzao\OneDrive\Documents\atlas\rust
cargo run -p mcp-market-data
```

Test the Python MCP client:

```powershell
cd c:\Users\ezzao\OneDrive\Documents\atlas
.\.venv\Scripts\python.exe -m protocols.mcp.client
```

### Phase 2 - Market Intelligence Agent

Implemented the first working specialist agent.

Flow:

```text
Natural language market query
  -> Granite plans MCP tool calls
  -> Python MCP client calls Rust server
  -> Rust server fetches Yahoo data
  -> Granite analyzes returned data
  -> Granite reflects on grounding
  -> Agent returns analysis, sources, confidence
```

Key files:

- `agents/base.py`
- `agents/market/agent.py`
- `agents/market/tools.py`
- `examples/market_agent_demo.py`

Run:

```powershell
# Terminal 1
cd c:\Users\ezzao\OneDrive\Documents\atlas\rust
cargo run -p mcp-market-data
```

```powershell
# Terminal 2
cd c:\Users\ezzao\OneDrive\Documents\atlas
.\.venv\Scripts\python.exe -m examples.market_agent_demo
```

### Phase 3 - A2A Protocol Layer

Implemented agent discovery and delegation over HTTP JSON-RPC.

Added:

- Agent Cards
- `GET /.well-known/agent.json`
- `POST /a2a`
- JSON-RPC methods:
  - `agent/card`
  - `tasks/send`
- A2A client
- Local Agent Card registry

Key files:

- `agents/market/agent_card.json`
- `agents/geopolitical/agent_card.json`
- `protocols/a2a/server.py`
- `protocols/a2a/client.py`
- `protocols/a2a/discovery.py`
- `examples/a2a_demo.py`

Run:

```powershell
# Terminal 1: Rust MCP server
cd c:\Users\ezzao\OneDrive\Documents\atlas\rust
cargo run -p mcp-market-data
```

```powershell
# Terminal 2: A2A demo
cd c:\Users\ezzao\OneDrive\Documents\atlas
.\.venv\Scripts\python.exe -m examples.a2a_demo
```

Expected behavior:

- Starts the Market Agent A2A server on `9001`
- Discovers the Market Agent Card
- Sends a task over `tasks/send`
- Receives a completed A2A artifact with grounded market analysis

### Phase 4 - Multi-Agent Coordination with Synthesis Agent

Implemented cross-agent orchestration.

Flow:

```text
User query
  -> LangGraph workflow
  -> Synthesis Agent
  -> Granite creates execution plan
  -> A2A delegates to Market, Geopolitical, Supply Chain agents
  -> Specialist agents return artifacts
  -> Granite synthesizes a unified briefing
```

Key files:

- `agents/geopolitical/agent.py`
- `agents/supply_chain/agent.py`
- `agents/supply_chain/agent_card.json`
- `agents/synthesis/planner.py`
- `agents/synthesis/agent.py`
- `orchestration/state.py`
- `orchestration/graph.py`
- `examples/synthesis_demo.py`

Run:

```powershell
# Terminal 1: Ollama / Granite
ollama run ibm/granite4.1:8b
```

```powershell
# Terminal 2: Rust MCP market data
cd c:\Users\ezzao\OneDrive\Documents\atlas\rust
cargo run -p mcp-market-data
```

```powershell
# Terminal 3: Full synthesis demo
cd c:\Users\ezzao\OneDrive\Documents\atlas
.\.venv\Scripts\python.exe -m examples.synthesis_demo
```

Expected behavior:

- Starts three A2A servers:
  - Market Agent: `9001`
  - Geopolitical Agent: `9002`
  - Supply Chain Agent: `9003`
- Loads Agent Cards
- Creates an execution plan
- Delegates tasks over A2A
- Uses live MCP/Yahoo data for market analysis
- Uses Granite model knowledge for geopolitical and supply-chain analysis
- Produces a synthesized Taiwan Strait semiconductor-risk briefing

## Full Chain of Command

```text
1. User runs examples.synthesis_demo
2. Demo starts A2A servers for specialist agents
3. LangGraph starts the synthesis workflow
4. Synthesis Agent asks Granite to create an execution plan
5. A2A client sends each task to the right specialist agent
6. Market Agent asks Granite which market tools/symbols to use
7. Market Agent calls the Rust MCP server through McpClient
8. Rust MCP server fetches Yahoo Finance chart data
9. Market Agent asks Granite to analyze and reflect on the data
10. Geopolitical and Supply Chain agents analyze with model knowledge and disclose live-data limits
11. Synthesis Agent collects all A2A artifacts
12. Granite writes a unified briefing with sources and confidence
```

## Current Demo Scenario

The Phase 4 demo runs the Taiwan Strait semiconductor exposure scenario:

```text
What's the exposure risk if Taiwan Strait tensions escalate?
Consider semiconductor supply chains and market impact.
```

The current output includes:

- Geopolitical risk assessment
- Supply-chain dependency assessment
- Live semiconductor market data
- Execution plan
- Per-agent sources
- Overall confidence

## Architecture Decisions

See [docs/DEVLOG.md](docs/DEVLOG.md) for the full ADR text.

| ADR | Phase | Decision |
|-----|-------|----------|
| ADR-001 | 0 | LangGraph orchestration + BeeAI per-agent construction |
| ADR-002 | 2 | Reflection loop depth and retry policy |
| ADR-003 | 3 | A2A transport: HTTP JSON-RPC 2.0 over gRPC for now |
| ADR-004 | 4 | Explicit DAG-shaped plan object schema |

## Next Phases

Planned from the PRD:

- Phase 5: Memory architecture
- Phase 6: Research & Filing Agent / EDGAR MCP server
- Phase 7: Guardian Agent
- Phase 8: Scheduled briefings
- Phase 9: Real-time alerts
- Phase 10: Observability
- Phase 11: CLI interface
- Phase 12: Web dashboard
- Phase 13: Full demo scenario
- Phase 14: Polish and presentation

## Notes

- The Market Agent currently has some demo-specific symbol guidance for semiconductor scenarios. This should eventually move into a general market symbol resolver.
- Geopolitical and Supply Chain agents currently use Granite model knowledge only; live MCP data sources are planned later.
- The Rust MCP server must be running before demos that require live market data.
- Ollama must be running before any Granite-backed agent call.
