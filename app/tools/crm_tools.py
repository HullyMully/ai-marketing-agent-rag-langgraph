"""CRM tools – the agent's interface to the mock CRM.

These functions model the *integration pattern* you would use with a real CRM
(HubSpot, Pipedrive, Zoho, ...). Instead of calling an external SaaS API, they
persist to a local SQLite-backed repository, which keeps the demo self-contained
and safe to publish (no real services, no secrets).
"""
from __future__ import annotations

from app.db.database import session_scope
from app.db.repositories import LeadRepository


def create_lead(
    *,
    name: str,
    contact: str,
    company: str | None = None,
    service_interest: str | None = None,
    budget_range: str | None = None,
    message: str | None = None,
) -> dict:
    """Create a lead in the mock CRM and return a serialisable summary.

    In a production system this is where you would POST to the CRM's REST API.
    """
    with session_scope() as db:
        lead = LeadRepository(db).create(
            name=name,
            contact=contact,
            company=company,
            service_interest=service_interest,
            budget_range=budget_range,
            message=message,
            status="new",
        )
        return {
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "contact": lead.contact,
            "service_interest": lead.service_interest,
            "status": lead.status,
        }


def get_service_info(retriever, query: str) -> dict:
    """Look up service information from the RAG knowledge base."""
    hits = retriever.search(query, top_k=3)
    return {"query": query, "results": [h.text for h in hits], "sources": [h.source for h in hits]}


def get_pricing_info(retriever, query: str = "pricing packages") -> dict:
    """Look up pricing information from the RAG knowledge base."""
    hits = retriever.search(query, top_k=3)
    return {"query": query, "results": [h.text for h in hits], "sources": [h.source for h in hits]}
