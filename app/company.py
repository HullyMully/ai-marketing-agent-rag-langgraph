"""Configurable business profile for the AI assistant.

The product is a generic, configurable AI customer assistant. A company's
identity is loaded from (in increasing priority):

1. built-in safe fallbacks,
2. ``config/company.example.json`` (the shipped sample profile),
3. environment variables (``COMPANY_NAME``, ``COMPANY_DOMAIN``, ...),
4. ``config/company.local.json`` (admin/runtime profile — git-ignored).

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
            "company_domain": self.company_domain,
            "company_description": self.company_description,
            "company_contact_email": self.company_contact_email,
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
    for key, env in _ENV_KEYS.items():
        value = os.environ.get(env)
        if value:
            data[key] = value
    data.update({k: v for k, v in _load_json(_CONFIG_DIR / "company.local.json").items() if k in data})
    return CompanyProfile(**{k: str(data.get(k, "")) for k in _FALLBACK})


_profile: CompanyProfile | None = None


def get_company() -> CompanyProfile:
    """Return a cached company profile."""
    global _profile
    if _profile is None:
        _profile = load_company_profile()
    return _profile


def profile_to_dict(profile: CompanyProfile) -> dict:
    """Return all non-secret editable company profile fields."""
    return {
        "product_name": PRODUCT_NAME,
        "company_name": profile.company_name,
        "company_domain": profile.company_domain,
        "company_description": profile.company_description,
        "company_contact_email": profile.company_contact_email,
        "assistant_name": profile.assistant_name,
        "escalation_target": profile.escalation_target,
        "business_industry": profile.business_industry,
        "brand_label": profile.brand_label,
    }


def save_company_profile(values: dict) -> CompanyProfile:
    """Persist editable company settings to the git-ignored local profile file."""
    global _profile
    current = {
        key: getattr(get_company(), key)
        for key in _FALLBACK
    }
    for key in _FALLBACK:
        if key in values:
            current[key] = str(values.get(key, "")).strip()

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = _CONFIG_DIR / "company.local.json"
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _profile = load_company_profile()
    return _profile
