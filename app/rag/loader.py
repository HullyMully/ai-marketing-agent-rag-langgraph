"""Document loading for the knowledge base."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    """A loaded source document."""

    source: str  # file name, e.g. "pricing.md"
    text: str


def load_markdown_dir(directory: str | Path) -> list[Document]:
    """Load all markdown files in a directory as Documents.

    LangChain's `DirectoryLoader` could be used here; we keep a tiny explicit
    loader so the project runs without optional system dependencies.
    """
    path = Path(directory)
    if not path.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {path}")

    docs: list[Document] = []
    for md_file in sorted(path.glob("*.md")):
        text = md_file.read_text(encoding="utf-8").strip()
        if text:
            docs.append(Document(source=md_file.name, text=text))
    return docs
