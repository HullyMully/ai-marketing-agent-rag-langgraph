"""Tests for the configurable business profile (app.company).

These verify the resolution order documented in ``app/company.py``:

    built-in fallbacks  <  company.example.json  <  company.local.json  <  env vars

The tests call :func:`load_company_profile` directly (it re-reads the config
files and the environment on every call) so they never touch the cached
singleton returned by :func:`get_company`.
"""
from __future__ import annotations

from app.company import (
    PRODUCT_NAME,
    CompanyProfile,
    _ENV_KEYS,
    _FALLBACK,
    load_company_profile,
)

_COMPANY_ENV_VARS = list(_ENV_KEYS.values())


def _clear_company_env(monkeypatch) -> None:
    for env in _COMPANY_ENV_VARS:
        monkeypatch.delenv(env, raising=False)


def test_fallbacks_are_generic_and_safe() -> None:
    # Built-in fallbacks must never embed a real or demo company.
    assert _FALLBACK["company_name"] == ""
    assert _FALLBACK["company_domain"].endswith(".example")
    assert _FALLBACK["company_contact_email"].endswith(".example")
    assert "novagrowth" not in str(_FALLBACK).lower()


def test_loads_example_profile_when_no_env(monkeypatch) -> None:
    # With no COMPANY_* env vars, values come from config/company.example.json.
    _clear_company_env(monkeypatch)
    profile = load_company_profile()
    assert profile.company_name == "Acme Growth Studio"
    assert profile.company_domain == "acme.example"
    assert profile.business_industry == "digital marketing"


def test_env_overrides_json_config(monkeypatch) -> None:
    _clear_company_env(monkeypatch)
    monkeypatch.setenv("COMPANY_NAME", "Bright Robotics")
    monkeypatch.setenv("BUSINESS_INDUSTRY", "industrial automation")
    profile = load_company_profile()
    assert profile.company_name == "Bright Robotics"
    assert profile.business_industry == "industrial automation"
    # Unset fields still fall back to the example profile.
    assert profile.company_domain == "acme.example"


def test_brand_label_uses_company_name(monkeypatch) -> None:
    _clear_company_env(monkeypatch)
    monkeypatch.setenv("COMPANY_NAME", "Bright Robotics")
    profile = load_company_profile()
    assert profile.brand_label == "Bright Robotics Assistant"
    assert profile.display_name == "Bright Robotics"


def test_brand_label_falls_back_to_product_name() -> None:
    # With no company name set, the brand is the generic product name and the
    # in-conversation reference is "our team" — never a demo brand.
    profile = CompanyProfile(**dict(_FALLBACK))
    assert profile.company_name == ""
    assert profile.brand_label == PRODUCT_NAME == "AI Customer Assistant"
    assert profile.display_name == "our team"


def test_public_dict_has_no_secrets(monkeypatch) -> None:
    _clear_company_env(monkeypatch)
    profile = load_company_profile()
    public = profile.public_dict()
    keys = " ".join(public).lower()
    assert "key" not in keys
    assert "token" not in keys
    assert "password" not in keys
    assert public["product_name"] == "AI Customer Assistant"
