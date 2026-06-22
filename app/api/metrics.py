"""Demo metrics endpoint computed from SQLite data."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import (
    LeadRepository,
    MessageRepository,
    TicketRepository,
)
from app.schemas.metrics import DemoMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/demo", response_model=DemoMetrics)
def demo_metrics(db: Session = Depends(get_db)) -> DemoMetrics:
    """Return aggregate demo metrics for the dashboard / portfolio."""
    messages = MessageRepository(db)
    conversations = messages.distinct_sessions()
    escalated_sessions = messages.escalated_count()
    leads = LeadRepository(db).count()
    tickets = TicketRepository(db).count()

    escalation_rate = (escalated_sessions / conversations) if conversations else 0.0
    resolved_by_ai_rate = 1.0 - escalation_rate

    return DemoMetrics(
        conversations=conversations,
        leads=leads,
        tickets=tickets,
        escalation_rate=round(escalation_rate, 3),
        resolved_by_ai_rate=round(resolved_by_ai_rate, 3),
    )
