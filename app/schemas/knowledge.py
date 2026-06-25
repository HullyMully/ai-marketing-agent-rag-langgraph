"""Schemas for knowledge-base admin endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeFileOut(BaseModel):
    """A markdown document in the configured knowledge base."""

    path: str
    size_bytes: int
    updated_at: datetime | None = None
    preview: str = ""


class KnowledgeFileContent(BaseModel):
    """Full markdown content for one knowledge-base document."""

    path: str
    content: str


class KnowledgeFileUpdate(BaseModel):
    """Create/update payload for a knowledge-base markdown file."""

    content: str = Field(default="")
