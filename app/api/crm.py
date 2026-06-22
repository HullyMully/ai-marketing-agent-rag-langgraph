"""Mock CRM endpoints for leads."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import LeadRepository
from app.schemas.crm import LeadCreate, LeadOut

router = APIRouter(prefix="/crm", tags=["crm"])


@router.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> LeadOut:
    """Create a lead in the mock CRM."""
    lead = LeadRepository(db).create(**payload.model_dump())
    return LeadOut.model_validate(lead)


@router.get("/leads", response_model=list[LeadOut])
def list_leads(db: Session = Depends(get_db)) -> list[LeadOut]:
    """List recent leads."""
    return [LeadOut.model_validate(lead) for lead in LeadRepository(db).list()]
