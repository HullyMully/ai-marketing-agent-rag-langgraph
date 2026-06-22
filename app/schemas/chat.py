"""Pydantic schemas for the chat endpoint."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message."""

    session_id: str = Field(..., description="Stable id for the conversation session.")
    user_message: str = Field(..., min_length=1, description="The user's message text.")
    user_id: str | None = Field(default=None, description="Optional external user id.")


class ChatResponse(BaseModel):
    """Agent reply plus useful debug/telemetry fields."""

    session_id: str
    answer: str
    intent: str
    escalated: bool = False
    action_taken: str | None = None
    created_lead_id: int | None = None
    created_ticket_id: int | None = None
    confidence: float = 1.0
    sources: list[str] = Field(default_factory=list)
