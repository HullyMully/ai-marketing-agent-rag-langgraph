"""Lightweight repository layer over the ORM models.

Keeping persistence logic here means API routers, tools and the agent never
talk to SQLAlchemy directly – they depend on small, testable functions.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Lead, Message, Ticket


# --------------------------------------------------------------------------- #
# Leads
# --------------------------------------------------------------------------- #
class LeadRepository:
    """CRUD operations for mock-CRM leads."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        contact: str,
        company: str | None = None,
        service_interest: str | None = None,
        budget_range: str | None = None,
        message: str | None = None,
        status: str = "new",
    ) -> Lead:
        lead = Lead(
            name=name,
            contact=contact,
            company=company,
            service_interest=service_interest,
            budget_range=budget_range,
            message=message,
            status=status,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def get(self, lead_id: int) -> Lead | None:
        return self.db.get(Lead, lead_id)

    def list(self, limit: int = 100) -> list[Lead]:
        stmt = select(Lead).order_by(Lead.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(Lead.id))) or 0)


# --------------------------------------------------------------------------- #
# Tickets
# --------------------------------------------------------------------------- #
class TicketRepository:
    """CRUD operations for support / escalation tickets."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str,
        reason: str,
        summary: str,
        priority: str = "normal",
        status: str = "open",
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            reason=reason,
            summary=summary,
            priority=priority,
            status=status,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def get(self, ticket_id: int) -> Ticket | None:
        return self.db.get(Ticket, ticket_id)

    def list(self, limit: int = 100) -> list[Ticket]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(Ticket.id))) or 0)


# --------------------------------------------------------------------------- #
# Conversation messages (memory + metrics)
# --------------------------------------------------------------------------- #
class MessageRepository:
    """Stores conversation turns for session memory and demo metrics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        intent: str | None = None,
        escalated: bool = False,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            intent=intent,
            escalated=1 if escalated else 0,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def history(self, session_id: str, limit: int = 20) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def distinct_sessions(self) -> int:
        return int(
            self.db.scalar(select(func.count(func.distinct(Message.session_id)))) or 0
        )

    def escalated_count(self) -> int:
        stmt = select(func.count(func.distinct(Message.session_id))).where(
            Message.escalated == 1
        )
        return int(self.db.scalar(stmt) or 0)
