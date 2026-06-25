"""Mock CRM endpoints for leads."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import (
    AuditLogRepository,
    CrmDispatchRepository,
    CrmIntegrationRepository,
    LeadRepository,
)
from app.schemas.crm import (
    CrmDispatchOut,
    CrmIntegrationOut,
    CrmIntegrationUpdate,
    LeadCreate,
    LeadOut,
)
from app.tools.crm_integrations import dispatch_lead_to_crm

router = APIRouter(prefix="/crm", tags=["crm"])


@router.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> LeadOut:
    """Create a lead in the mock CRM."""
    lead = LeadRepository(db).create(**payload.model_dump())
    AuditLogRepository(db).create(
        actor="api",
        action="lead.created",
        entity_type="lead",
        entity_id=lead.id,
        summary=f"API created lead #{lead.id} for {lead.company or lead.name}",
    )
    dispatch_lead_to_crm(LeadOut.model_validate(lead).model_dump(mode="json"))
    return LeadOut.model_validate(lead)


@router.get("/leads", response_model=list[LeadOut])
def list_leads(db: Session = Depends(get_db)) -> list[LeadOut]:
    """List recent leads."""
    return [LeadOut.model_validate(lead) for lead in LeadRepository(db).list()]


@router.get("/integration", response_model=CrmIntegrationOut)
def get_crm_integration(db: Session = Depends(get_db)) -> CrmIntegrationOut:
    """Return outbound CRM integration settings."""
    return CrmIntegrationOut.model_validate(CrmIntegrationRepository(db).get())


@router.put("/integration", response_model=CrmIntegrationOut)
def update_crm_integration(
    payload: CrmIntegrationUpdate,
    db: Session = Depends(get_db),
) -> CrmIntegrationOut:
    """Update outbound CRM integration settings."""
    integration = CrmIntegrationRepository(db).update(**payload.model_dump())
    AuditLogRepository(db).create(
        actor="admin",
        action="crm_integration.updated",
        entity_type="crm_integration",
        entity_id=integration.id,
        summary=f"Updated CRM integration: {integration.provider}",
        metadata=payload.model_dump(),
    )
    return CrmIntegrationOut.model_validate(integration)


@router.get("/dispatches", response_model=list[CrmDispatchOut])
def list_crm_dispatches(db: Session = Depends(get_db)) -> list[CrmDispatchOut]:
    """List recent outbound CRM sync attempts."""
    return [CrmDispatchOut.model_validate(row) for row in CrmDispatchRepository(db).list()]
