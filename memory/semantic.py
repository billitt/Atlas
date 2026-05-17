"""Semantic memory backed by ChromaDB and Ollama embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from services.embeddings import embed_texts


class SemanticMemory:
    """Persistent vector memory for documents and retrieved context."""

    def __init__(self, collection_name: str = "atlas", persist_dir: str = "data/chroma") -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        """Chunk, embed, and store documents in ChromaDB."""
        chunks: list[str] = []
        chunk_metadatas: list[dict[str, Any]] = []
        chunk_ids: list[str] = []

        for text, metadata, doc_id in zip(texts, metadatas, ids, strict=True):
            for index, chunk in enumerate(_chunk_text(text)):
                chunks.append(chunk)
                chunk_metadatas.append({**metadata, "source_id": doc_id, "chunk_index": index})
                chunk_ids.append(f"{doc_id}::chunk-{index}")

        if not chunks:
            return

        embeddings = embed_texts(chunks)
        self.collection.upsert(
            documents=chunks,
            metadatas=chunk_metadatas,
            ids=chunk_ids,
            embeddings=embeddings,
        )

    def query(self, text: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Return nearest semantic matches as text/metadata/distance dicts."""
        query_embedding = embed_texts([text])[0]
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        matches: list[dict[str, Any]] = []
        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            matches.append(
                {
                    "text": document,
                    "metadata": metadata or {},
                    "distance": distance,
                }
            )
        return matches

    def count(self) -> int:
        return self.collection.count()


def _chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Simple character chunker until a tokenizer-aware splitter is needed."""
    stripped = text.strip()
    if not stripped:
        return []
    if len(stripped) <= max_chars:
        return [stripped]

    chunks: list[str] = []
    start = 0
    while start < len(stripped):
        end = min(start + max_chars, len(stripped))
        chunks.append(stripped[start:end].strip())
        if end == len(stripped):
            break
        start = max(0, end - overlap)
    return chunks
