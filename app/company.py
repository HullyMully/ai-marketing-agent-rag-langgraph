"""Configurable business profile for the AI assistant.

The product is a generic, configurable AI customer assistant. A company's
identity is loaded from (in increasing priority):

1. built-in safe fallbacks,
2. ``config/company.example.json`` (the shipped sample profile),
3. ``config/company.local.json`` (a real deployment's profile — git-ignored),
4. environment variables (``COMPANY_NAME``, ``COMPANY_DOMAIN``, ...).

Nothing here is secret; LLM/API keys live only in the environment, never in the
company profile.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()  # populate os.environ from .env (real env vars win)
except Exception:  # pragma: no cover - dotenv optional at import time
    pass

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

_FALLBACK = {
    "company_name": "",
    "company_domain": "your-domain.example",
    "company_description": "a small business",
    "company_contact_email": "support@your-domain.example",
    "assistant_name": "AI Assistant",
    "escalation_target": "human manager",
    "business_industry": "",
}

# Maps profile keys to their environment-variable names.
_ENV_KEYS = {
    "company_name": "COMPANY_NAME",
    "company_domain": "COMPANY_DOMAIN",
    "company_description": "COMPANY_DESCRIPTION",
    "company_contact_email": "COMPANY_CONTACT_EMAIL",
    "assistant_name": "DEFAULT_ASSISTANT_NAME",
    "escalation_target": "DEFAULT_ESCALATION_TARGET",
    "business_industry": "BUSINESS_INDUSTRY",
}

# Product-level (not company-specific) display strings.
PRODUCT_NAME = "AI Customer Assistant"


@dataclass(frozen=True)
class CompanyProfile:
    """Resolved business profile used across the app and UI."""

    company_name: str
    company_domain: str
    company_description: str
    company_contact_email: str
    assistant_name: str
    escalation_target: str
    business_industry: str

    @property
    def display_name(self) -> str:
        """Name to refer to the company in conversation ('our team' if unset)."""
        return self.company_name or "our team"

    @property
    def brand_label(self) -> str:
        """Header brand: '<Company> Assistant', or the generic product name."""
        return f"{self.company_name} Assistant" if self.company_name else PRODUCT_NAME

    def public_dict(self) -> dict:
        """Non-secret fields safe to expose to the browser."""
        return {
            "product_name": PRODUCT_NAME,
            "company_name": self.company_name,
            "company_description": self.company_description,
            "business_industry": self.business_industry,
            "assistant_name": self.assistant_name,
            "escalation_target": self.escalation_target,
            "brand_label": self.brand_label,
        }


def _load_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def load_company_profile() -> CompanyProfile:
    """Resolve the company profile from fallbacks, JSON files and env vars."""
    data = dict(_FALLBACK)
    data.update({k: v for k, v in _load_json(_CONFIG_DIR / "company.example.json").items() if k in data})
    data.update({k: v for k, v in _load_json(_CONFIG_DIR / "company.local.json").items() if k in data})
    for key, env in _ENV_KEYS.items():
        value = os.environ.get(env)
        if value:
            data[key] = value
    return CompanyProfile(**{k: str(data.get(k, "")) for k in _FALLBACK})


_profile: CompanyProfile | None = None


def get_company() -> CompanyProfile:
    """Return a cached company profile."""
    global _profile
    if _profile is None:
        _profile = load_company_profile()
    return _profile
