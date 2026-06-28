"""Hardware-aware runtime configuration for Atlas.

Atlas runs several specialist agents that each call the same local Granite model
through Ollama. To use the host efficiently without overcommitting it, we size
the number of agents Atlas fans out concurrently to the machine it runs on, then
cache that decision so it is computed once (per hardware profile) on first run.

This module never mutates system state or the Ollama server. It only:
  - detects CPU/RAM/platform,
  - computes a recommended parallelism (clamped to the agent count),
  - persists the result to ``data/runtime_config.json`` with a hardware
    signature and an "acknowledged" flag,
  - and formats a one-time recommendation for ``OLLAMA_NUM_PARALLEL``.

Applying ``OLLAMA_NUM_PARALLEL`` is left to the user because it is read by the
``ollama serve`` process at startup and requires a restart (and, on some
platforms, elevated privileges) to take effect.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

# Approximate resident footprint of ibm/granite4.1:8b at Q4 (weights), in GB.
MODEL_FOOTPRINT_GB = 5.5
# Approximate extra memory per concurrent request slot (KV cache), in GB.
KV_PER_SLOT_GB = 1.0
# Fraction of total RAM we are willing to budget for the model + slots.
MEMORY_BUDGET_FRACTION = 0.6
# Hard cap: there are four specialist agents; more parallelism than that gives
# no benefit for the current fan-out and only contends for one GPU.
MAX_CONCURRENCY = 4
# Conservative fallback when total memory cannot be detected.
FALLBACK_MEM_TOTAL_GB = 16.0

CONFIG_PATH = Path("data/runtime_config.json")
CONCURRENCY_ENV_OVERRIDE = "ATLAS_AGENT_CONCURRENCY"


def _detect_total_memory_gb() -> float:
    """Total physical RAM in GB, using psutil when available."""
    try:
        import psutil

        return psutil.virtual_memory().total / (1024**3)
    except Exception:
        # Best-effort POSIX fallback; otherwise a conservative default.
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            return (page_size * phys_pages) / (1024**3)
        except (ValueError, AttributeError, OSError):
            return FALLBACK_MEM_TOTAL_GB


def detect_hardware() -> JsonDict:
    """Return a snapshot of the host hardware relevant to inference sizing."""
    system = platform.system()
    machine = platform.machine()
    return {
        "cpu_logical": os.cpu_count() or 1,
        "mem_total_gb": round(_detect_total_memory_gb(), 1),
        "system": system,
        "machine": machine,
        "is_apple_silicon": system == "Darwin" and machine in ("arm64", "aarch64"),
    }


def recommend_parallelism(hardware: JsonDict) -> int:
    """Pick a safe concurrent-agent count for this machine, clamped to [1, MAX]."""
    override = os.getenv(CONCURRENCY_ENV_OVERRIDE)
    if override:
        try:
            return max(1, min(MAX_CONCURRENCY, int(override)))
        except ValueError:
            pass

    mem_total = float(hardware.get("mem_total_gb") or FALLBACK_MEM_TOTAL_GB)
    cpu_logical = int(hardware.get("cpu_logical") or 1)

    mem_budget = mem_total * MEMORY_BUDGET_FRACTION
    by_mem = int((mem_budget - MODEL_FOOTPRINT_GB) / KV_PER_SLOT_GB)
    by_cpu = cpu_logical // 2

    candidate = min(by_mem, by_cpu, MAX_CONCURRENCY)
    return max(1, min(MAX_CONCURRENCY, candidate))


def _signature(hardware: JsonDict) -> str:
    return (
        f"{hardware.get('cpu_logical')}-{hardware.get('mem_total_gb')}"
        f"-{hardware.get('system')}-{hardware.get('machine')}"
    )


def _load_cache() -> JsonDict | None:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(config: JsonDict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except OSError:
        # A read-only filesystem must not break the pipeline; we simply lose
        # the cache and recompute next run.
        pass


def get_runtime_config() -> JsonDict:
    """Return the cached runtime config, recomputing if missing or stale.

    The cache is invalidated when the hardware signature changes (e.g. the
    project is cloned onto a different machine), which also resets the
    ``acknowledged`` flag so the recommendation is shown again.
    """
    hardware = detect_hardware()
    signature = _signature(hardware)
    cached = _load_cache()

    if cached and cached.get("signature") == signature:
        # Keep recommended value fresh if the env override changed.
        recommended = recommend_parallelism(hardware)
        if cached.get("recommended_parallel") != recommended:
            cached["recommended_parallel"] = recommended
            _write_cache(cached)
        return cached

    config: JsonDict = {
        "signature": signature,
        "hardware": hardware,
        "recommended_parallel": recommend_parallelism(hardware),
        "acknowledged": False,
    }
    _write_cache(config)
    return config


def recommended_concurrency() -> int:
    """Number of specialist agents Atlas may run concurrently on this host."""
    return int(get_runtime_config().get("recommended_parallel", 1) or 1)


def needs_recommendation_prompt() -> bool:
    """True when the one-time recommendation has not been acknowledged yet."""
    return not bool(get_runtime_config().get("acknowledged", False))


def mark_acknowledged() -> None:
    """Record that the user has seen and accepted the recommendation."""
    config = get_runtime_config()
    config["acknowledged"] = True
    _write_cache(config)


def format_recommendation_message(config: JsonDict | None = None) -> str:
    """Human-readable first-run recommendation, including the Ollama hint."""
    config = config or get_runtime_config()
    hardware = config.get("hardware") or {}
    n = int(config.get("recommended_parallel", 1) or 1)
    cpu = hardware.get("cpu_logical", "?")
    mem = hardware.get("mem_total_gb", "?")

    return (
        f"Detected {cpu} logical CPUs and {mem} GB RAM. "
        f"Atlas will run up to {n} specialist agent(s) in parallel.\n"
        f"For the best speedup, configure Ollama to match and restart it:\n"
        f"  - macOS:   launchctl setenv OLLAMA_NUM_PARALLEL {n}  (then restart Ollama)\n"
        f"  - Windows: setx OLLAMA_NUM_PARALLEL {n}              (then restart Ollama)\n"
        f"  - Linux:   set OLLAMA_NUM_PARALLEL={n} for the ollama service, then restart\n"
        f"Optional: set OLLAMA_KEEP_ALIVE=30m so the model stays loaded between calls.\n"
        f"Atlas works regardless of this setting; without it, parallel requests just "
        f"queue inside Ollama."
    )
