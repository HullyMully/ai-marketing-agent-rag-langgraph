"""Qdrant-backed vector store with an in-memory fallback.

Qdrant is the primary vector database (run via Docker Compose). When Qdrant is
not reachable, the store transparently falls back to an in-memory index so the
RAG pipeline and tests still run anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.rag.embeddings import EmbeddingProvider


@dataclass
class SearchHit:
    """A single retrieval result."""

    text: str
    source: str
    score: float


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class InMemoryVectorStore:
    """Tiny cosine-similarity index used as a fallback / for tests."""

    def __init__(self) -> None:
        self._vectors: list[list[float]] = []
        self._payloads: list[dict] = []

    def reset(self) -> None:
        self._vectors.clear()
        self._payloads.clear()

    def upsert(self, vectors: list[list[float]], payloads: list[dict]) -> None:
        self._vectors.extend(vectors)
        self._payloads.extend(payloads)

    def search(self, vector: list[float], top_k: int = 3) -> list[SearchHit]:
        scored = [
            (_cosine(vector, v), p) for v, p in zip(self._vectors, self._payloads)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(text=p["text"], source=p["source"], score=float(s))
            for s, p in scored[:top_k]
        ]


class QdrantVectorStore:
    """Vector store backed by a real Qdrant instance."""

    def __init__(self, dim: int) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qmodels

        self._qmodels = qmodels
        self._client = QdrantClient(url=settings.qdrant_url)
        self._collection = settings.qdrant_collection
        self._dim = dim

    def reset(self) -> None:
        self._client.recreate_collection(
            collection_name=self._collection,
            vectors_config=self._qmodels.VectorParams(
                size=self._dim, distance=self._qmodels.Distance.COSINE
            ),
        )

    def upsert(self, vectors: list[list[float]], payloads: list[dict]) -> None:
        points = [
            self._qmodels.PointStruct(id=i, vector=vec, payload=payload)
            for i, (vec, payload) in enumerate(zip(vectors, payloads))
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def search(self, vector: list[float], top_k: int = 3) -> list[SearchHit]:
        results = self._client.search(
            collection_name=self._collection, query_vector=vector, limit=top_k
        )
        hits: list[SearchHit] = []
        for result in results:
            payload = result.payload or {}
            text = payload.get("text")
            source = payload.get("source")
            if isinstance(text, str) and isinstance(source, str):
                hits.append(SearchHit(text=text, source=source, score=float(result.score)))
        return hits


def get_vector_store(embedder: EmbeddingProvider):
    """Return a Qdrant store if reachable, otherwise an in-memory fallback."""
    try:
        store = QdrantVectorStore(dim=embedder.dim)
        # Touch the server to confirm connectivity.
        store._client.get_collections()
        return store
    except Exception:
        return InMemoryVectorStore()
