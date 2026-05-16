# Atlas

Global business intelligence platform powered by protocol-native AI agents (MCP + A2A), LangGraph orchestration, and IBM Granite on Ollama.

See [PRD.md](PRD.md) for architecture and build phases.

## Phase 0 — Environment setup (complete)

Phase 0 verified 2026-05-16. See [docs/DEVLOG.md](docs/DEVLOG.md) for run logs and ADR-001.

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/download)
- NVIDIA GPU recommended (Granite 4.1 8B Q4 ~5.3 GB VRAM)

### 1. Pull Granite

```powershell
# If ollama is not on PATH (Windows):
# & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull ibm/granite4.1:8b
ollama pull ibm/granite4.1:8b
```

### 2. Python environment

```powershell
cd atlas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

### 3. Verify Ollama + Granite

```powershell
python -m scripts.verify_ollama
```

### 4. Hello worlds

```powershell
python -m examples.langgraph_hello
python -m examples.beeai_hello
```

Or via entry points after install:

```powershell
atlas-verify-ollama
atlas-langgraph-hello
atlas-beeai-hello
```
