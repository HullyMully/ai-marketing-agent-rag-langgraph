"""Support-ticket tools used by the agent."""
from __future__ import annotations

from app.db.database import session_scope
from app.db.repositories import AuditLogRepository, TicketRepository


def create_ticket(
    *,
    user_id: str,
    reason: str,
    summary: str,
    priority: str = "normal",
) -> dict:
    """Create a support ticket and return a serialisable summary."""
    with session_scope() as db:
        ticket = TicketRepository(db).create(
            user_id=user_id, reason=reason, summary=summary, priority=priority
        )
        AuditLogRepository(db).create(
            actor="assistant",
            action="ticket.created",
            entity_type="ticket",
            entity_id=ticket.id,
            summary=f"Assistant created ticket #{ticket.id}: {reason}",
        )
        return {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "reason": ticket.reason,
            "priority": ticket.priority,
            "status": ticket.status,
        }


def get_ticket_status(ticket_id: int) -> dict | None:
    """Return the current status of a ticket, or None if not found."""
    with session_scope() as db:
        ticket = TicketRepository(db).get(ticket_id)
        if ticket is None:
            return None
        return {"id": ticket.id, "status": ticket.status, "priority": ticket.priority}
