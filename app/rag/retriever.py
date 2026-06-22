"""Retriever – ties embeddings + vector store into a simple search API.

A module-level singleton keeps an in-memory index warm inside the FastAPI
process so chat requests can retrieve without re-embedding the corpus.
"""
from __future__ import annotations

from app.config import settings
from app.rag.embeddings import get_embedding_provider
from app.rag.loader import load_markdown_dir
from app.rag.splitter import split_documents
from app.rag.vectorstore import InMemoryVectorStore, SearchHit, get_vector_store


class KnowledgeRetriever:
    """Embeds a query and returns the most relevant knowledge-base chunks."""

    def __init__(self) -> None:
        self._embedder = get_embedding_provider()
        self._store = get_vector_store(self._embedder)
        self._ready = False

    @property
    def embedding_mode(self) -> str:
        return type(self._embedder).__name__

    @property
    def store_mode(self) -> str:
        return type(self._store).__name__

    def index_knowledge_base(self, directory: str | None = None) -> dict:
        """Load, chunk, embed and upsert the knowledge base. Returns stats."""
        directory = directory or settings.knowledge_base_dir
        docs = load_markdown_dir(directory)
        chunks = split_documents(docs)
        vectors = self._embedder.embed([c.text for c in chunks])
        payloads = [{"text": c.text, "source": c.source} for c in chunks]

        self._store.reset()
        self._store.upsert(vectors, payloads)
        self._ready = True
        return {
            "documents": len(docs),
            "chunks": len(chunks),
            "collection": settings.qdrant_collection,
            "embedding_mode": self.embedding_mode,
            "store_mode": self.store_mode,
        }

    def ensure_ready(self) -> None:
        """Lazily index the corpus into the in-memory fallback if needed."""
        if self._ready:
            return
        if isinstance(self._store, InMemoryVectorStore):
            self.index_knowledge_base()

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        """Return the top-k most relevant chunks for a query."""
        self.ensure_ready()
        vector = self._embedder.embed([query])[0]
        return self._store.search(vector, top_k=top_k)


_retriever: KnowledgeRetriever | None = None


def get_retriever() -> KnowledgeRetriever:
    """Return a process-wide singleton retriever."""
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever
