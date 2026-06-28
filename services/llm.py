"""Ollama / IBM Granite LLM client shared by LangGraph and BeeAI examples."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from observability.tracing import get_tracer

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "ibm/granite4.1:8b")
BEEAI_MODEL_NAME = os.getenv("LLM_CHAT_MODEL_NAME", f"ollama:{OLLAMA_CHAT_MODEL}")


def get_chat_ollama(**kwargs: Any) -> ChatOllama:
    """LangChain ChatOllama pointed at local Granite."""
    return ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_CHAT_MODEL,
        temperature=0.2,
        **kwargs,
    )


def chat(prompt: str) -> str:
    """Single-turn chat via LangChain; returns assistant text."""
    tracer = get_tracer("services.llm")
    with tracer.start_as_current_span("llm.chat") as span:
        span.set_attribute("prompt_length", len(prompt))
        span.set_attribute("model_name", OLLAMA_CHAT_MODEL)
        llm = get_chat_ollama()
        response = llm.invoke([HumanMessage(content=prompt)])
        text = str(response.content)
        span.set_attribute("response_length", len(text))
        return text


def ollama_generate(prompt: str, *, model: str | None = None) -> str:
    """Direct Ollama REST call (used by verify script and health checks)."""
    model = model or OLLAMA_CHAT_MODEL
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=120.0) as client:
        response = client.post("/api/generate", json=payload)
        response.raise_for_status()
        return response.json()["response"]


def list_models() -> list[str]:
    """Return model names available in the local Ollama instance."""
    with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=10.0) as client:
        response = client.get("/api/tags")
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
