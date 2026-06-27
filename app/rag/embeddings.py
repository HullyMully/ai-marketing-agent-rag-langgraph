"""Embedding providers.

Two implementations:

* `OpenAIEmbeddingProvider` – real embeddings via an OpenAI-compatible API.
* `MockEmbeddingProvider`  – a deterministic, dependency-free hashing embedding
  used for offline demo mode (USE_MOCK_EMBEDDINGS=true). It is NOT semantically
  strong, but it is stable and lets the full RAG pipeline run without API keys.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from pydantic.v1 import SecretStr

from app.config import settings


class EmbeddingProvider(Protocol):
    """Common interface for embedding providers."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common English stopwords are filtered out so the deterministic demo embedding
# keys on meaningful terms instead of being dominated by "the", "to", "you"...
_STOPWORDS = frozenset(
    """a an and the to of for in on at is are be by or our we you your with that
    this it as do does how can from will not no they their them what who which
    when where why all any more most other some such only own same so than too
    very i im were was has have had about into out up down""".split()
)


class MockEmbeddingProvider:
    """Deterministic bag-of-words hashing embeddings (offline demo mode).

    Not semantically strong, but stable and dependency-free. Stopwords are
    removed so retrieval keys on meaningful terms; this is enough to make the
    RAG pipeline demonstrably rank the right documents without API keys.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            if token in _STOPWORDS or len(token) < 2:
                continue
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class OpenAIEmbeddingProvider:
    """Real embeddings through an OpenAI-compatible endpoint via LangChain."""

    def __init__(self) -> None:
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=SecretStr(settings.openai_api_key),
            base_url=settings.openai_base_url,
        )
        # text-embedding-3-small -> 1536 dims; allow override via settings.
        self.dim = settings.embedding_dim if settings.embedding_dim else 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed_documents(texts)


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider."""
    if settings.use_mock_embeddings or settings.mock_llm:
        return MockEmbeddingProvider(dim=settings.embedding_dim or 384)
    return OpenAIEmbeddingProvider()
