"""Escalation tool – routes complex cases to a human manager.

Escalation is modelled as a high-priority support ticket. In a real deployment
this might also notify a Slack channel or page an on-call manager.
"""
from __future__ import annotations

from app.tools.ticket_tools import create_ticket


def escalate_to_human(
    *,
    user_id: str,
    summary: str,
    reason: str = "human_escalation",
    priority: str = "high",
) -> dict:
    """Create a high-priority escalation ticket for a human manager."""
    return create_ticket(
        user_id=user_id, reason=reason, summary=summary, priority=priority
    )
