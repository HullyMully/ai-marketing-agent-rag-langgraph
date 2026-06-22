"""Pydantic schema for the demo metrics endpoint."""
from __future__ import annotations

from pydantic import BaseModel


class DemoMetrics(BaseModel):
    """Aggregate demo metrics computed from SQLite data."""

    conversations: int
    leads: int
    tickets: int
    escalation_rate: float
    resolved_by_ai_rate: float


class KnowledgeIngestResult(BaseModel):
    """Result of a knowledge-base ingestion run."""

    documents: int
    chunks: int
    collection: str
    embedding_mode: str
