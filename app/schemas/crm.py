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


class CrmIntegrationUpdate(BaseModel):
    """Editable outbound CRM integration settings.

    Secrets are referenced by environment-variable name, not stored directly.
    """

    provider: str = Field(default="local", max_length=60)
    enabled: bool = False
    webhook_url: str | None = Field(default=None, max_length=500)
    api_key_env: str | None = Field(default=None, max_length=120)
    pipeline_name: str | None = Field(default=None, max_length=120)


class CrmIntegrationOut(CrmIntegrationUpdate):
    """Persisted outbound CRM integration settings."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None


class CrmDispatchOut(BaseModel):
    """A recorded attempt to sync a lead to an external CRM."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int | None
    provider: str
    status: str
    response_summary: str | None
    created_at: datetime
