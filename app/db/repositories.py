"""Lightweight repository layer over the ORM models.

Keeping persistence logic here means API routers, tools and the agent never
talk to SQLAlchemy directly – they depend on small, testable functions.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    CrmDispatch,
    CrmIntegration,
    Lead,
    Message,
    Ticket,
    TicketNote,
)


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

    def update(
        self,
        ticket_id: int,
        *,
        status: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
    ) -> Ticket | None:
        ticket = self.get(ticket_id)
        if ticket is None:
            return None
        if status is not None:
            ticket.status = status
        if priority is not None:
            ticket.priority = priority
        if assignee is not None:
            ticket.assignee = assignee or None
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def add_note(self, ticket_id: int, *, author: str, body: str) -> TicketNote:
        note = TicketNote(ticket_id=ticket_id, author=author, body=body)
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def notes(self, ticket_id: int, limit: int = 100) -> list[TicketNote]:
        stmt = (
            select(TicketNote)
            .where(TicketNote.ticket_id == ticket_id)
            .order_by(TicketNote.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(Ticket.id))) or 0)


# --------------------------------------------------------------------------- #
# CRM integrations
# --------------------------------------------------------------------------- #
class CrmIntegrationRepository:
    """Stores outbound CRM integration settings."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> CrmIntegration:
        integration = self.db.get(CrmIntegration, 1)
        if integration is None:
            integration = CrmIntegration(id=1, provider="local", enabled=0)
            self.db.add(integration)
            self.db.commit()
            self.db.refresh(integration)
        return integration

    def update(
        self,
        *,
        provider: str,
        enabled: bool,
        webhook_url: str | None = None,
        api_key_env: str | None = None,
        pipeline_name: str | None = None,
    ) -> CrmIntegration:
        integration = self.get()
        integration.provider = provider
        integration.enabled = 1 if enabled else 0
        integration.webhook_url = webhook_url or None
        integration.api_key_env = api_key_env or None
        integration.pipeline_name = pipeline_name or None
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration


class CrmDispatchRepository:
    """Records outbound CRM sync attempts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        lead_id: int | None,
        provider: str,
        status: str,
        response_summary: str | None = None,
    ) -> CrmDispatch:
        dispatch = CrmDispatch(
            lead_id=lead_id,
            provider=provider,
            status=status,
            response_summary=response_summary,
        )
        self.db.add(dispatch)
        self.db.commit()
        self.db.refresh(dispatch)
        return dispatch

    def list(self, limit: int = 100) -> list[CrmDispatch]:
        stmt = select(CrmDispatch).order_by(CrmDispatch.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
class AuditLogRepository:
    """Append-only admin/operator audit trail."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        action: str,
        entity_type: str,
        summary: str,
        actor: str = "system",
        entity_id: str | int | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=summary,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False) if metadata else None,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list(self, limit: int = 100) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))


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
