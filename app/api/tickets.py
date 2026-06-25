"""Support / escalation ticket endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import AuditLogRepository, TicketRepository
from app.schemas.tickets import (
    TicketCreate,
    TicketNoteCreate,
    TicketNoteOut,
    TicketOut,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketOut:
    """Create a support / escalation ticket."""
    ticket = TicketRepository(db).create(**payload.model_dump())
    AuditLogRepository(db).create(
        actor="assistant" if payload.reason == "human_escalation" else "api",
        action="ticket.created",
        entity_type="ticket",
        entity_id=ticket.id,
        summary=f"Created ticket #{ticket.id}: {ticket.reason}",
    )
    return TicketOut.model_validate(ticket)


@router.get("", response_model=list[TicketOut])
def list_tickets(db: Session = Depends(get_db)) -> list[TicketOut]:
    """List recent tickets."""
    return [TicketOut.model_validate(t) for t in TicketRepository(db).list()]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    """Fetch a single ticket by id."""
    ticket = TicketRepository(db).get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketOut.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
) -> TicketOut:
    """Update ticket inbox fields such as status, priority and assignee."""
    ticket = TicketRepository(db).update(ticket_id, **payload.model_dump())
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    AuditLogRepository(db).create(
        actor="operator",
        action="ticket.updated",
        entity_type="ticket",
        entity_id=ticket.id,
        summary=f"Updated ticket #{ticket.id}",
        metadata=payload.model_dump(exclude_none=True),
    )
    return TicketOut.model_validate(ticket)


@router.get("/{ticket_id}/notes", response_model=list[TicketNoteOut])
def list_ticket_notes(ticket_id: int, db: Session = Depends(get_db)) -> list[TicketNoteOut]:
    """List internal notes for one support ticket."""
    if TicketRepository(db).get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return [TicketNoteOut.model_validate(n) for n in TicketRepository(db).notes(ticket_id)]


@router.post("/{ticket_id}/notes", response_model=TicketNoteOut, status_code=201)
def add_ticket_note(
    ticket_id: int,
    payload: TicketNoteCreate,
    db: Session = Depends(get_db),
) -> TicketNoteOut:
    """Add an internal operator note to a ticket."""
    repo = TicketRepository(db)
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    note = repo.add_note(ticket_id, author=payload.author, body=payload.body)
    AuditLogRepository(db).create(
        actor=payload.author,
        action="ticket_note.created",
        entity_type="ticket",
        entity_id=ticket_id,
        summary=f"Added note to ticket #{ticket_id}",
    )
    return TicketNoteOut.model_validate(note)
