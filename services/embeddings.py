"""Ollama embedding client used by Atlas semantic memory."""

from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from services.llm import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL

load_dotenv()

OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "granite-embedding:278m")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text batches through Ollama `/api/embed`.

    Atlas prefers `OLLAMA_EMBED_MODEL` for semantic memory. If that model is not
    pulled yet, we retry with the chat model so demos can still run on a minimal
    Ollama setup. Pulling the embedding model is still recommended for quality.
    """
    if not texts:
        return []

    clean_texts = [text if text.strip() else " " for text in texts]
    try:
        return _embed_with_model(clean_texts, OLLAMA_EMBED_MODEL)
    except Exception as exc:
        if OLLAMA_EMBED_MODEL == OLLAMA_CHAT_MODEL:
            raise
        print(
            "[embeddings] "
            f"Embedding model {OLLAMA_EMBED_MODEL!r} failed ({exc}); "
            f"falling back to chat model {OLLAMA_CHAT_MODEL!r}."
        )
        return _embed_with_model(clean_texts, OLLAMA_CHAT_MODEL)


def _embed_with_model(texts: list[str], model: str) -> list[list[float]]:
    payload: dict[str, Any] = {"model": model, "input": texts}
    with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=120.0) as client:
        response = client.post("/api/embed", json=payload)
        response.raise_for_status()
        body = response.json()

    embeddings = body.get("embeddings")
    if not isinstance(embeddings, list):
        raise RuntimeError(f"Ollama embed response missing embeddings: {body!r}")
    return embeddings
