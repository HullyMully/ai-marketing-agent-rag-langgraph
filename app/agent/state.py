"""Shared state object passed between LangGraph nodes."""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Mutable state threaded through the conversation graph.

    `total=False` lets nodes populate fields incrementally.
    """

    # --- inputs ---
    session_id: str
    user_id: str | None
    user_message: str
    history: list[dict[str, str]]

    # --- classification ---
    intent: str
    confidence: float

    # --- routing ---
    route: str

    # --- retrieval ---
    retrieved: list[str]
    sources: list[str]

    # --- lead collection ---
    slots: dict[str, Any]
    missing_fields: list[str]

    # --- outputs / side effects ---
    answer: str
    action_taken: str | None
    escalated: bool
    created_lead_id: int | None
    created_ticket_id: int | None
