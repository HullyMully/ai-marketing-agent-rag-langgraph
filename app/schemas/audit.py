"""Schemas for admin/operator audit log events."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


class AuditLogOut(BaseModel):
    """Audit event returned to the admin UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    metadata_json: str | None = None
    created_at: datetime

    @computed_field
    @property
    def metadata(self) -> dict[str, Any]:
        if not self.metadata_json:
            return {}
        try:
            value = json.loads(self.metadata_json)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
