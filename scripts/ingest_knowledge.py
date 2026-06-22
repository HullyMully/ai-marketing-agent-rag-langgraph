"""Ingest the knowledge base into the vector database.

Usage:
    python scripts/ingest_knowledge.py

Works in demo mode (mock embeddings + in-memory fallback) with no API keys,
and against a real Qdrant instance when one is reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script: `python scripts/ingest_knowledge.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.retriever import get_retriever  # noqa: E402


def main() -> None:
    retriever = get_retriever()
    print(f"Embedding mode : {retriever.embedding_mode}")
    stats = retriever.index_knowledge_base()
    print("Knowledge base ingested:")
    print(f"  documents     : {stats['documents']}")
    print(f"  chunks        : {stats['chunks']}")
    print(f"  collection    : {stats['collection']}")
    print(f"  vector store  : {stats['store_mode']}")
    print("Done.")


if __name__ == "__main__":
    main()
