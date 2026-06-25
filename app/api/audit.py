"""Admin audit log endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import AuditLogRepository
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditLogOut])
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    """List recent admin/operator audit events."""
    return [AuditLogOut.model_validate(row) for row in AuditLogRepository(db).list(limit)]
