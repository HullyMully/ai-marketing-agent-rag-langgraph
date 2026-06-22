"""Session-based conversation memory.

Message history is persisted to SQLite (so it survives restarts and feeds the
demo metrics). Lead-qualification "slots" collected during a conversation are
kept in a lightweight in-process store keyed by session id, behind a clear
interface so the backend could be swapped later.
"""
from __future__ import annotations

import re

from app.db.database import session_scope
from app.db.repositories import MessageRepository

# Lead fields the agent tries to fill before creating a CRM lead.
LEAD_SLOTS = ["name", "company", "contact", "service_interest", "budget_range"]
REQUIRED_SLOTS = ["name", "contact"]

# In-process slot memory: {session_id: {slot: value}}.
_SLOT_STORE: dict[str, dict[str, str]] = {}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NAME_RE = re.compile(r"\b(?i:my name is|i am|i'm|this is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)")
_COMPANY_RE = re.compile(
    r"\b(?i:company is|company:|work at|we are|we're)\s+"
    r"([A-Z][A-Za-z0-9&]+(?:\s+[A-Z][A-Za-z0-9&]+){0,3})"
)
_BUDGET_RE = re.compile(
    r"\$\s?[\d,]+\s?[km]?(?:\s?/?\s?(?:per month|a month|months|month|mo))?",
    re.IGNORECASE,
)

_SERVICE_KEYWORDS = {
    "Paid Advertising": ["ppc", "paid ads", "google ads", "meta ads", "ads", "advertising"],
    "SEO": ["seo", "search engine", "ranking", "organic"],
    "Content Marketing": ["content", "blog", "articles"],
    "Social Media Management": ["social media", "instagram", "tiktok", "social"],
    "Email & Lifecycle Marketing": ["email marketing", "newsletter", "klaviyo", "lifecycle"],
}


class ConversationMemory:
    """Clear interface over message history + lead slots for one session."""

    def add_turn(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_id: str | None = None,
        intent: str | None = None,
        escalated: bool = False,
    ) -> None:
        with session_scope() as db:
            MessageRepository(db).add(
                session_id=session_id,
                role=role,
                content=content,
                user_id=user_id,
                intent=intent,
                escalated=escalated,
            )

    def history(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        with session_scope() as db:
            rows = MessageRepository(db).history(session_id, limit=limit)
            return [{"role": r.role, "content": r.content} for r in rows]

    # --- lead slots ---------------------------------------------------------
    def get_slots(self, session_id: str) -> dict[str, str]:
        return dict(_SLOT_STORE.get(session_id, {}))

    def update_slots(self, session_id: str, values: dict[str, str]) -> dict[str, str]:
        store = _SLOT_STORE.setdefault(session_id, {})
        for key, value in values.items():
            if value:
                store[key] = value
        return dict(store)

    def clear_slots(self, session_id: str) -> None:
        _SLOT_STORE.pop(session_id, None)

    def missing_required(self, session_id: str) -> list[str]:
        slots = self.get_slots(session_id)
        return [s for s in REQUIRED_SLOTS if not slots.get(s)]


def extract_slots(message: str) -> dict[str, str]:
    """Best-effort extraction of lead fields from a single message.

    Heuristic and intentionally simple; in production an LLM with structured
    output would handle this more robustly.
    """
    found: dict[str, str] = {}

    email = _EMAIL_RE.search(message)
    if email:
        found["contact"] = email.group(0)

    name = _NAME_RE.search(message)
    if name:
        found["name"] = name.group(1).strip()

    company = _COMPANY_RE.search(message)
    if company:
        found["company"] = company.group(1).strip().rstrip(".")

    budget = _BUDGET_RE.search(message)
    if budget:
        found["budget_range"] = budget.group(0).strip()

    lowered = message.lower()
    for service, keywords in _SERVICE_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            found["service_interest"] = service
            break

    return found


_memory: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    """Return a process-wide singleton memory instance."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
