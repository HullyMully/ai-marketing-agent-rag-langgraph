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

    # --- understanding / lead draft ---
    extracted: dict[str, Any]
    saved_fields: list[str]
    user_confusion: bool
    correction_detected: bool
    asks_for_human: bool
    clarification_count: int
    lead_draft: dict[str, Any]
    missing_fields: list[str]
    lead_created: bool
    lead_id: int | None

    # --- dialogue policy ---
    mode: str                      # answering / exploring / qualifying / paused
    exploration_mode: bool
    qualification_paused: bool
    known_interests: list[str]
    next_step: str
    dialogue_state: dict[str, Any]

    # --- retrieval ---
    retrieved: list[str]
    sources: list[str]
    memory_used: bool

    # --- outputs / side effects ---
    answer: str
    action_taken: str | None
    escalated: bool
    ticket_created: bool
    created_lead_id: int | None
    created_ticket_id: int | None
