"""Outbound CRM integration dispatch.

The local CRM remains the source of truth for the demo. When an integration is
enabled, this module records and optionally sends the new lead to an external
webhook-compatible CRM adapter.
"""
from __future__ import annotations

import json
import os
from urllib import request
from urllib.error import URLError

from app.db.database import session_scope
from app.db.repositories import CrmDispatchRepository, CrmIntegrationRepository


def dispatch_lead_to_crm(lead: dict) -> dict:
    """Dispatch one lead to the configured outbound CRM integration."""
    with session_scope() as db:
        integration = CrmIntegrationRepository(db).get()
        config = {
            "provider": integration.provider or "local",
            "enabled": bool(integration.enabled),
            "webhook_url": integration.webhook_url,
            "api_key_env": integration.api_key_env,
        }

    if not config["enabled"]:
        return _record_dispatch(
            lead_id=lead.get("id"),
            provider=config["provider"],
            status="skipped",
            response_summary="CRM integration disabled",
        )

    if config["provider"] == "webhook" and config["webhook_url"]:
        return _send_webhook(config["webhook_url"], config["api_key_env"], lead)

    return _record_dispatch(
        lead_id=lead.get("id"),
        provider=config["provider"],
        status="skipped",
        response_summary=f"Provider {config['provider']} is configured but no adapter is enabled",
    )


def _send_webhook(url: str, api_key_env: str | None, lead: dict) -> dict:
    token = os.environ.get(api_key_env or "") if api_key_env else ""
    payload = json.dumps({"lead": lead}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=5) as resp:  # noqa: S310 - admin-configured URL
            summary = f"Webhook returned HTTP {resp.status}"
        status = "success"
    except (OSError, URLError) as exc:
        summary = f"Webhook failed: {type(exc).__name__}"
        status = "failed"
    return _record_dispatch(
        lead_id=lead.get("id"),
        provider="webhook",
        status=status,
        response_summary=summary,
    )


def _record_dispatch(
    *,
    lead_id: int | None,
    provider: str,
    status: str,
    response_summary: str,
) -> dict:
    with session_scope() as db:
        row = CrmDispatchRepository(db).create(
            lead_id=lead_id,
            provider=provider,
            status=status,
            response_summary=response_summary,
        )
        return {
            "id": row.id,
            "lead_id": row.lead_id,
            "provider": row.provider,
            "status": row.status,
            "response_summary": row.response_summary,
        }
