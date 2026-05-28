# Atlas Memory

Three-tier memory architecture: semantic vectors, episodic records, and working scratchpad.

---

## Overview

| Tier | Technology | Path | Mutability | Purpose |
|------|------------|------|------------|---------|
| **Semantic** | ChromaDB | `data/chroma/` | Upsert | Similarity search over documents |
| **Episodic** | SQLite + SQLModel | `data/sqlite/atlas_episodic.db` | Append-only | Audit trail, temporal reasoning |
| **Working** | In-process dict | Per-query state | Ephemeral | LangGraph scratchpad |

Design rationale: ADR-005.

---

## Tier 1: Semantic Memory

**Module:** `memory/semantic.py` — `SemanticMemory`

### How it works

1. Documents are chunked (max 1200 chars, 150 overlap)
2. Chunks embedded via Ollama (`granite-embedding:278m`)
3. Stored in ChromaDB with metadata
4. Queries embed the question and return nearest neighbors

### API

```python
memory = SemanticMemory(collection_name="atlas", persist_dir="data/chroma")
memory.add_documents(texts, metadatas, ids)
results = memory.query("Taiwan Strait semiconductor risk", n_results=5)
memory.count()
```

### Query during agent execution

Agents call semantic memory in `execute()` before Granite analysis:

| Agent | Filter | Example metadata |
|-------|--------|------------------|
| Market | General context | `source=yahoo`, prior analyses |
| Geopolitical | `category=geopolitical`, `source=seed_gdelt` | Taiwan scenario events |
| Supply Chain | `category=supply_chain`, `source=seed_comtrade` | Trade flow, chokepoints |
| Research | Filing chunks | `source=sec_edgar`, `accession_number` |

Matched excerpts are injected into the Granite prompt; metadata becomes `sources` in `AgentResult`.

### Concrete example (Taiwan demo)

After `load_taiwan_scenario()`:

```python
matches = memory.query("Taiwan Strait tension TSMC", n_results=3)
# Returns GDELT event summaries, aggregate HIGH risk metrics, chokepoint data
```

---

## Tier 2: Episodic Memory

**Module:** `memory/episodic.py` — `EpisodicMemory`

Append-only SQLite store. Enables questions like *"What did we assess last week?"* and briefing deltas.

### Schema: BriefingRecord

| Column | Type | Description |
|--------|------|-------------|
| `id` | int PK | Auto-increment |
| `timestamp` | datetime | When briefing was generated |
| `query` | str | Original query or topic query |
| `briefing_type` | str | `daily`, `weekly`, `custom` |
| `topics` | JSON list | Watchlist topics |
| `plan` | JSON | Execution plan |
| `agent_results` | JSON | Per-agent outputs (includes Guardian verdict) |
| `final_briefing` | str | Combined analysis text |
| `confidence` | str | Overall confidence |
| `sources` | JSON | Per-agent source lists |
| `delta_from_last` | str | Change from prior briefing on same topic |
| `trace_id` | str | OpenTelemetry trace link |
| `duration_seconds` | float | Pipeline duration |

### Schema: AlertRecord

| Column | Type | Description |
|--------|------|-------------|
| `id` | int PK | Auto-increment |
| `timestamp` | datetime | When alert fired |
| `rule_id` | str | Alert rule identifier |
| `rule_name` | str | Human-readable name |
| `trigger` | str | Trigger description |
| `severity` | str | HIGH / MEDIUM / LOW |
| `summary` | str | Alert summary |
| `evidence` | str | Supporting evidence |
| `context` | str | Operational context note |
| `sources` | JSON | Data sources used |

### Schema: AgentExecution

| Column | Type | Description |
|--------|------|-------------|
| `id` | int PK | Auto-increment |
| `timestamp` | datetime | Execution time |
| `agent_name` | str | Specialist name |
| `task` | str | Delegated task |
| `result` | JSON | Full AgentResult |
| `confidence` | str | Final confidence |
| `duration_seconds` | float | Execution time |

### Temporal reasoning APIs

```python
episodic = EpisodicMemory()
episodic.get_last_briefing("Taiwan Strait semiconductor risk")
episodic.query_briefings("semiconductor", limit=10)
episodic.get_confidence_history("Taiwan", days=90)
episodic.briefing_count()
```

**Delta example:** First briefing on a topic returns *"No prior briefing found; baseline created."* Subsequent runs compare confidence and reference prior record ID.

---

## Tier 3: Working Memory

**Module:** `memory/working.py` — `WorkingMemory`

Simple key-value scratchpad for a single query session:

```python
wm = WorkingMemory()
wm.add("plan", execution_plan)
wm.get("plan")
wm.to_context_string()  # inject into prompts
wm.clear()
```

Used in demos and available for LangGraph state extensions. Not persisted across requests.

---

## Data Flow

```text
Seed loader / Research agent
        │
        ▼
  Semantic Memory (ChromaDB)
        │
        ▼
  Agent execute() queries relevant chunks
        │
        ▼
  Synthesis merges agent results
        │
        ▼
  Episodic Memory logs BriefingRecord + AgentExecution
        │
        ▼
  Run logger writes runs/YYYYMMDD_HHMMSS.json
```

---

## Related Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — memory in system context
- [DATA_SOURCES.md](DATA_SOURCES.md) — seed data ingestion
- [AGENTS.md](AGENTS.md) — per-agent memory usage
