"""Session memory: conversation history + a persistent lead draft.

The lead draft is the structured dialogue state gathered while qualifying a
prospect. It survives across messages in the same session (kept in-process,
behind a clear interface). History is persisted to SQLite for metrics.
"""
from __future__ import annotations

from app.db.database import session_scope
from app.db.repositories import MessageRepository

# Required for a CRM lead. Budget may instead be explicitly marked unknown.
REQUIRED_FIELDS = ["name", "company", "contact_email", "service_interest", "budget_range"]
# Fields shown in the UI lead draft (includes optional ones).
DISPLAY_FIELDS = [
    "name", "company", "contact_email", "service_interest", "budget_range",
    "product_type",
]


def _empty_draft() -> dict:
    return {
        "name": "",
        "company": "",
        "contact_email": "",
        "phone": "",
        "service_interest": "",
        "budget_range": "",
        "product_type": "",
        "notes": "",
        "budget_unknown": False,
        "lead_created": False,
        "lead_id": None,
        # --- dialogue state ---
        "last_asked": [],        # fields the assistant most recently asked for
        "clarify_count": 0,      # consecutive truly-unclear messages
        "greeting_count": 0,     # how many social greetings the user sent
        "repeated_question_count": 0,  # times the current question type repeated
        "last_question_type": "",      # type of the last question we asked
        "user_refused_count": 0,       # "no", "not now", "later"...
        "user_confusion_count": 0,     # "I don't remember", "idk"...
        "user_frustration_count": 0,   # ALL CAPS refusal, "stop asking"...
        "qualification_paused": False, # stop asking for lead details
        "exploration_mode": False,     # help the user think, don't qualify
        "qualification_active": False, # the user wants to start a request
        "last_assistant_summary": "",  # short summary of our previous reply
    }


_DRAFT_STORE: dict[str, dict] = {}

_FIELD_KEYS = (
    "name", "company", "contact_email", "phone", "service_interest",
    "budget_range", "product_type", "notes",
)


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

    def update_draft(self, session_id: str, values: dict) -> tuple[dict, list[str]]:
        """Merge values into the draft. Returns (draft, newly_saved_field_keys)."""
        draft = _DRAFT_STORE.setdefault(session_id, _empty_draft())
        newly_saved: list[str] = []
        for key, value in values.items():
            if key == "budget_unknown":
                if value:
                    draft["budget_unknown"] = True
                continue
            if key in _FIELD_KEYS and value:
                if draft.get(key) != value:
                    newly_saved.append(key)
                draft[key] = value
        return dict(draft), newly_saved

    def set_last_asked(self, session_id: str, fields: list[str]) -> None:
        _DRAFT_STORE.setdefault(session_id, _empty_draft())["last_asked"] = list(fields)

    def get_last_asked(self, session_id: str) -> list[str]:
        return list(self.get_draft(session_id).get("last_asked", []))

    def known_fields(self, session_id: str) -> dict[str, str]:
        draft = self.get_draft(session_id)
        return {k: draft[k] for k in DISPLAY_FIELDS if draft.get(k)}

    def has_any_field(self, session_id: str) -> bool:
        draft = self.get_draft(session_id)
        return any(draft.get(k) for k in _FIELD_KEYS)

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

    # --- clarification attempts --------------------------------------------
    def clarify_count(self, session_id: str) -> int:
        return int(self.get_draft(session_id).get("clarify_count", 0))

    def bump_clarify(self, session_id: str) -> int:
        draft = _DRAFT_STORE.setdefault(session_id, _empty_draft())
        draft["clarify_count"] = int(draft.get("clarify_count", 0)) + 1
        return draft["clarify_count"]

    def reset_clarify(self, session_id: str) -> None:
        if session_id in _DRAFT_STORE:
            _DRAFT_STORE[session_id]["clarify_count"] = 0

    # --- dialogue state -----------------------------------------------------
    def _live(self, session_id: str) -> dict:
        return _DRAFT_STORE.setdefault(session_id, _empty_draft())

    def get(self, session_id: str, key: str, default=None):
        return self.get_draft(session_id).get(key, default)

    def bump(self, session_id: str, key: str) -> int:
        draft = self._live(session_id)
        draft[key] = int(draft.get(key, 0)) + 1
        return draft[key]

    def set_flag(self, session_id: str, key: str, value) -> None:
        self._live(session_id)[key] = value

    def dialogue_state(self, session_id: str) -> dict:
        """Public snapshot of the dialogue-tracking counters/flags."""
        d = self.get_draft(session_id)
        keys = (
            "greeting_count", "repeated_question_count", "last_question_type",
            "user_refused_count", "user_confusion_count", "user_frustration_count",
            "qualification_paused", "exploration_mode", "qualification_active",
            "last_assistant_summary",
        )
        return {k: d.get(k) for k in keys}

    def note_question(self, session_id: str, qtype: str) -> int:
        """Record that we asked a question of `qtype`. Returns how many times in a
        row this same question type has now been asked (1 = first time)."""
        draft = self._live(session_id)
        if qtype and draft.get("last_question_type") == qtype:
            draft["repeated_question_count"] = int(draft.get("repeated_question_count", 0)) + 1
        else:
            draft["repeated_question_count"] = 1
        draft["last_question_type"] = qtype
        return draft["repeated_question_count"]

    def times_asked(self, session_id: str, qtype: str) -> int:
        """How many consecutive times `qtype` has been asked already (0 if a
        different question was asked last)."""
        draft = self.get_draft(session_id)
        if draft.get("last_question_type") != qtype:
            return 0
        return int(draft.get("repeated_question_count", 0))


_memory: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    """Return a process-wide singleton memory instance."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
