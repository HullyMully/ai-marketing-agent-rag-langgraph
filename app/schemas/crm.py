"""Pydantic schemas for the mock CRM."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    """Payload to create a CRM lead."""

    name: str = Field(..., min_length=1)
    contact: str = Field(..., min_length=1, description="Email or phone.")
    company: str | None = None
    service_interest: str | None = None
    budget_range: str | None = None
    message: str | None = None
    status: str = "new"


class LeadOut(BaseModel):
    """CRM lead as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company: str | None
    contact: str
    service_interest: str | None
    budget_range: str | None
    message: str | None
    status: str
    created_at: datetime
