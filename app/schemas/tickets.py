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


class TicketOut(BaseModel):
    """Ticket as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    reason: str
    summary: str
    priority: str
    status: str
    created_at: datetime
