"""Chunking of documents for embedding & retrieval.

Uses LangChain's RecursiveCharacterTextSplitter so the project demonstrates the
standard LangChain RAG building blocks.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loader import Document


@dataclass
class Chunk:
    """A chunk of text with provenance back to its source document."""

    source: str
    text: str


def split_documents(
    documents: list[Document], chunk_size: int = 700, chunk_overlap: int = 120
) -> list[Chunk]:
    """Split documents into overlapping chunks, preserving the source name."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks: list[Chunk] = []
    for doc in documents:
        for piece in splitter.split_text(doc.text):
            piece = piece.strip()
            if piece:
                chunks.append(Chunk(source=doc.source, text=piece))
    return chunks
