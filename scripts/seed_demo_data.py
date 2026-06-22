"""Seed the SQLite database with synthetic demo leads and tickets.

Usage:
    python scripts/seed_demo_data.py

All data is fictional and safe to publish.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import init_db, session_scope  # noqa: E402
from app.db.repositories import (  # noqa: E402
    LeadRepository,
    MessageRepository,
    TicketRepository,
)

DEMO_LEADS = [
    dict(name="Alex Rivera", company="BrightBean Coffee", contact="alex@brightbean.example",
         service_interest="Paid Advertising", budget_range="$1,500-$5,000",
         message="Want to run Google Ads for our online store."),
    dict(name="Priya Shah", company="Lumen Yoga Studio", contact="priya@lumenyoga.example",
         service_interest="SEO", budget_range="under $1,500",
         message="Need help ranking locally."),
    dict(name="Tom Becker", company="DeltaSaaS", contact="tom@deltasaas.example",
         service_interest="Content Marketing", budget_range="$3,500+",
         message="Looking for a B2B content engine."),
]

DEMO_TICKETS = [
    dict(user_id="demo-user-1", reason="human_escalation",
         summary="Client asked to speak with an account manager about a refund.",
         priority="high"),
    dict(user_id="demo-user-2", reason="out_of_scope",
         summary="Question about enterprise SLA not covered by knowledge base.",
         priority="normal"),
]


def main() -> None:
    init_db()
    with session_scope() as db:
        leads = LeadRepository(db)
        for payload in DEMO_LEADS:
            leads.create(**payload)
        tickets = TicketRepository(db)
        for payload in DEMO_TICKETS:
            tickets.create(**payload)
        messages = MessageRepository(db)
        messages.add(session_id="demo-session-1", role="user",
                     content="What services do you offer?", intent="service_question")
        messages.add(session_id="demo-session-1", role="assistant",
                     content="We offer PPC, SEO, content, social and email marketing.",
                     intent="service_question")
    print(f"Seeded {len(DEMO_LEADS)} leads and {len(DEMO_TICKETS)} tickets.")


if __name__ == "__main__":
    main()
