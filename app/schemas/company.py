"""Schemas for editable company profile settings."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyProfileUpdate(BaseModel):
    """Editable non-secret business profile fields."""

    company_name: str = Field(default="", max_length=120)
    company_domain: str = Field(default="", max_length=160)
    company_description: str = Field(default="", max_length=500)
    company_contact_email: str = Field(default="", max_length=160)
    assistant_name: str = Field(default="AI Assistant", max_length=120)
    escalation_target: str = Field(default="human manager", max_length=120)
    business_industry: str = Field(default="", max_length=160)

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, value):
        if value is None:
            return ""
        return str(value).strip()


class CompanyProfileOut(CompanyProfileUpdate):
    """Resolved company profile returned to the admin UI."""

    model_config = ConfigDict(extra="ignore")

    product_name: str = "AI Customer Assistant"
    brand_label: str = "AI Customer Assistant"
