"""Pydantic schemas for the chat endpoint."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message."""

    session_id: str = Field(..., description="Stable id for the conversation session.")
    user_message: str = Field(..., min_length=1, description="The user's message text.")
    user_id: str | None = Field(default=None, description="Optional external user id.")


class ChatResponse(BaseModel):
    """Agent reply plus clean product metadata for the UI."""

    session_id: str
    answer: str
    intent: str
    action: str | None = None

    # Lead qualification
    lead_draft: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    lead_created: bool = False
    lead_id: int | None = None

    # Escalation
    ticket_created: bool = False
    ticket_id: int | None = None

    # Knowledge / memory
    sources: list[str] = Field(default_factory=list)
    memory_used: bool = False

    # Telemetry (kept for compatibility)
    escalated: bool = False
    confidence: float = 1.0
