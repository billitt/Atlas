"""Semantic memory backed by ChromaDB and Ollama embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import InvalidArgumentError

from services.embeddings import embed_texts


class SemanticMemory:
    """Persistent vector memory for documents and retrieved context."""

    def __init__(self, collection_name: str = "atlas", persist_dir: str = "data/chroma") -> None:
        self._collection_name = collection_name
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
        self._upsert_chunks(chunks, chunk_metadatas, chunk_ids, embeddings)

    def _recreate_collection(self, embedding_dim: int) -> None:
        print(
            f"[semantic] Embedding dimension changed; recreating collection "
            f"{self._collection_name!r} (dim={embedding_dim})."
        )
        self.client.delete_collection(self._collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self._collection_name,
            metadata={"embedding_dim": str(embedding_dim)},
        )

    def _ensure_embedding_dimension(self, embedding_dim: int) -> None:
        if self.collection.count() == 0:
            return
        meta = self.collection.metadata or {}
        stored = meta.get("embedding_dim")
        if stored is not None and int(stored) != embedding_dim:
            self._recreate_collection(embedding_dim)
            return
        try:
            peek = self.collection.peek(limit=1, include=["embeddings"])
            embs = peek.get("embeddings") or []
            if embs and embs[0] is not None and len(embs[0]) != embedding_dim:
                self._recreate_collection(embedding_dim)
        except Exception:
            return

    def _upsert_chunks(
        self,
        chunks: list[str],
        chunk_metadatas: list[dict[str, Any]],
        chunk_ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        embedding_dim = len(embeddings[0]) if embeddings else 0
        self._ensure_embedding_dimension(embedding_dim)
        try:
            self.collection.upsert(
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
                embeddings=embeddings,
            )
        except InvalidArgumentError as exc:
            if "dimension" not in str(exc).lower():
                raise
            self._recreate_collection(embedding_dim)
            self.collection.upsert(
                documents=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
                embeddings=embeddings,
            )
        if embedding_dim and not (self.collection.metadata or {}).get("embedding_dim"):
            try:
                self.collection.modify(metadata={"embedding_dim": str(embedding_dim)})
            except Exception:
                pass

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

    def has(self, doc_id: str) -> bool:
        """True when any chunk for ``doc_id`` already exists in the collection.

        Chunks are stored with ids like ``{doc_id}::chunk-{index}``, so an exact
        id check would miss them; match on the id prefix instead.
        """
        try:
            existing = self.collection.get(ids=[f"{doc_id}::chunk-0"])
            return bool(existing.get("ids"))
        except Exception:
            return False


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
