"""Pydantic schemas for support / escalation tickets."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    """Payload to create a support / escalation ticket."""

    user_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    priority: str = "normal"
    status: str = "open"


class TicketUpdate(BaseModel):
    """Fields an operator can update from the human inbox."""

    status: str | None = None
    priority: str | None = None
    assignee: str | None = None


class TicketNoteCreate(BaseModel):
    """Internal note added by a human operator."""

    author: str = Field(default="operator", min_length=1)
    body: str = Field(..., min_length=1)


class TicketOut(BaseModel):
    """Ticket as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    reason: str
    summary: str
    priority: str
    status: str
    assignee: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TicketNoteOut(BaseModel):
    """Internal ticket note returned to the admin inbox."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author: str
    body: str
    created_at: datetime
