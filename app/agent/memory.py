"""Session-based conversation memory and a lead-qualification draft.

Message history is persisted to SQLite (so it survives restarts and feeds the
demo metrics). The per-session **lead draft** — the fields gathered while
qualifying a prospect — is kept in a lightweight in-process store keyed by
session id, behind a clear interface so the backend could be swapped later.
"""
from __future__ import annotations

import re

from app.db.database import session_scope
from app.db.repositories import MessageRepository

# Fields a lead draft can hold. A CRM lead is only created once the required
# ones are all known (budget may be explicitly marked unknown).
LEAD_FIELDS = ["name", "company", "contact_email", "service_interest", "budget_range"]
REQUIRED_FIELDS = ["name", "company", "contact_email", "service_interest", "budget_range"]


def _empty_draft() -> dict:
    return {
        "name": "",
        "company": "",
        "contact_email": "",
        "service_interest": "",
        "budget_range": "",
        "notes": "",
        "budget_unknown": False,
        "lead_created": False,
        "lead_id": None,
    }


# In-process draft store: {session_id: draft}.
_DRAFT_STORE: dict[str, dict] = {}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NAME_RE = re.compile(r"\b(?i:my name is|i am|i'm|this is|name is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)")
_BARE_NAME_RE = re.compile(r"^\s*([A-Z][a-z]{1,20})\b")
_COMPANY_RE = re.compile(
    r"\b(?i:company is|company:|work at|i'm from|i am from|i'm with|i am with|"
    r"here at|we are|we're|from)\s+"
    r"([A-Z][A-Za-z0-9&]+(?:\s+[A-Z][A-Za-z0-9&]+){0,3})"
)
_BUDGET_RE = re.compile(
    r"\$\s?[\d,]+\s?[km]?(?:\s?/?\s?(?:per month|a month|months|month|mo))?",
    re.IGNORECASE,
)
_BUDGET_UNKNOWN_RE = re.compile(
    r"(?i)\b(?:no budget|budget is unknown|not sure (?:about|of)?\s*(?:the|my)?\s*budget|"
    r"don'?t have a budget|budget tbd|no set budget|unsure (?:about|of) budget)\b"
)

# Words that should never be mistaken for a first name in the bare-name path.
_NOT_NAMES = {
    "hi", "hello", "hey", "company", "budget", "my", "the", "contact", "email",
    "we", "our", "i", "yes", "no", "ok", "okay", "thanks", "sure", "paid", "seo",
}

_SERVICE_KEYWORDS = {
    "Paid acquisition": ["paid ads", "paid acquisition", "ppc", "google ads", "meta ads", "ads", "advertising"],
    "Landing page audit": ["landing page", "landing-page", "page audit"],
    "Analytics setup": ["analytics", "tracking setup", "ga4", "conversion tracking"],
    "Campaign optimization": ["campaign optimization", "optimize campaign", "optimisation", "optimization"],
    "SEO": ["seo", "search engine", "organic ranking"],
    "Content marketing": ["content marketing", "blog", "articles"],
    "Email marketing": ["email marketing", "newsletter", "lifecycle"],
    "Social media": ["social media", "instagram", "tiktok"],
}


class ConversationMemory:
    """Message history + a per-session lead draft."""

    # --- message history ----------------------------------------------------
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
                session_id=session_id, role=role, content=content,
                user_id=user_id, intent=intent, escalated=escalated,
            )

    def history(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        with session_scope() as db:
            rows = MessageRepository(db).history(session_id, limit=limit)
            return [{"role": r.role, "content": r.content} for r in rows]

    # --- lead draft ---------------------------------------------------------
    def get_draft(self, session_id: str) -> dict:
        return dict(_DRAFT_STORE.get(session_id, _empty_draft()))

    def update_draft(self, session_id: str, values: dict) -> dict:
        draft = _DRAFT_STORE.setdefault(session_id, _empty_draft())
        for key, value in values.items():
            if key == "budget_unknown":
                if value:
                    draft["budget_unknown"] = True
            elif value:
                draft[key] = value
        return dict(draft)

    def known_fields(self, session_id: str) -> dict[str, str]:
        draft = self.get_draft(session_id)
        return {k: draft[k] for k in LEAD_FIELDS if draft.get(k)}

    def missing_fields(self, session_id: str) -> list[str]:
        draft = self.get_draft(session_id)
        missing: list[str] = []
        for field in REQUIRED_FIELDS:
            if field == "budget_range":
                if not draft.get("budget_range") and not draft.get("budget_unknown"):
                    missing.append(field)
            elif not draft.get(field):
                missing.append(field)
        return missing

    def is_lead_created(self, session_id: str) -> bool:
        return bool(self.get_draft(session_id).get("lead_created"))

    def lead_id(self, session_id: str) -> int | None:
        return self.get_draft(session_id).get("lead_id")

    def mark_lead_created(self, session_id: str, lead_id: int) -> None:
        draft = _DRAFT_STORE.setdefault(session_id, _empty_draft())
        draft["lead_created"] = True
        draft["lead_id"] = lead_id

    def reset_draft(self, session_id: str) -> None:
        _DRAFT_STORE.pop(session_id, None)


def extract_fields(message: str) -> dict:
    """Best-effort extraction of lead fields from one message."""
    found: dict = {}

    email = _EMAIL_RE.search(message)
    if email:
        found["contact_email"] = email.group(0)

    name = _NAME_RE.search(message)
    if name:
        found["name"] = name.group(1).strip()
    elif email:
        # "Sam, sam@brightdesk.example" — accept a leading capitalised word.
        bare = _BARE_NAME_RE.match(message)
        if bare and bare.group(1).lower() not in _NOT_NAMES:
            found["name"] = bare.group(1)

    company = _COMPANY_RE.search(message)
    if company:
        found["company"] = company.group(1).strip().rstrip(".")

    if _BUDGET_UNKNOWN_RE.search(message):
        found["budget_unknown"] = True
    else:
        budget = _BUDGET_RE.search(message)
        if budget:
            found["budget_range"] = budget.group(0).strip()

    lowered = message.lower()
    for service, keywords in _SERVICE_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            found["service_interest"] = service
            break

    return found


# Backwards-compatible alias (older imports).
extract_slots = extract_fields


_memory: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    """Return a process-wide singleton memory instance."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
