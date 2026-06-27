"""Backend action-validation layer.

The LLM planner only *recommends* actions. Before the backend executes any
side-effect (creating a CRM lead, opening an escalation ticket) the
recommendation is checked here against deterministic business rules. The
planner can never create a lead or ticket on its own — these functions are the
single source of truth for whether an action is allowed to run.

Each check returns a :class:`ValidationResult` describing whether the action is
allowed, a machine-readable ``reason`` (used to generate a natural assistant
reply when the action is rejected), and any ``missing_fields``.

Nothing here produces a user-facing phrase: the reason codes are internal and
are handed to the LLM, which writes the actual reply.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Fields a CRM lead requires before it can be created.
LEAD_REQUIRED_FIELDS = ("name", "company", "contact_email", "service_interest", "budget_range")

# Messages that must NEVER, on their own, open an escalation ticket.
# Phrases that, on their own, are never an escalation: ordinary confusion,
# greetings, restating, "new customer", etc. A real human request or genuine
# frustration overrides these (handled before the check runs).
_TICKET_NEVER_HINTS = (
    "what do you mean",
    "i don't remember",
    "i dont remember",
    "i told you",
    "i told u",
    "i am a new customer",
    "i'm a new customer",
    "new customer",
    "another one",
    "say hello",
    "good morning",
    "good afternoon",
    "good evening",
)
# Bare greetings that must not escalate.
_GREETING_ONLY = {"hi", "hello", "hey", "yo", "hiya", "howdy", "greetings", "another one"}
# Signals that a request genuinely needs a human / custom review.
_ENTERPRISE_HINTS = ("enterprise", "custom workflow", "custom enterprise")


@dataclass
class ValidationResult:
    """Outcome of validating a recommended backend action."""

    allowed: bool
    reason: str = ""
    missing_fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "missing_fields": list(self.missing_fields),
        }


def _valid_email(value: str | None) -> bool:
    """A pragmatic email check (matches the rest of the codebase)."""
    if not value:
        return False
    value = value.strip()
    if "@" not in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain


# --------------------------------------------------------------------------- #
# Lead creation
# --------------------------------------------------------------------------- #
def validate_lead_creation(
    *,
    draft: dict,
    lead_created: bool,
    recommended_action: str,
    user_agrees_to_proceed: bool,
) -> ValidationResult:
    """Decide whether a CRM lead may be created.

    A lead may be created only if ALL of the following hold:

    * the planner recommended ``create_lead``;
    * no lead has been created for this session yet (no duplicates);
    * a name, a company, a valid email and a service interest are all present;
    * a budget range is present, OR the budget is explicitly unknown *and* the
      user has agreed to proceed without one.
    """
    if recommended_action != "create_lead":
        return ValidationResult(False, reason="action_not_recommended")

    if lead_created:
        # A lead already exists for this session — never create a duplicate.
        return ValidationResult(False, reason="lead_already_exists")

    draft = draft or {}
    missing: list[str] = []

    if not draft.get("name"):
        missing.append("name")
    if not draft.get("company"):
        missing.append("company")
    if not _valid_email(draft.get("contact_email")):
        missing.append("contact_email")
    if not draft.get("service_interest"):
        missing.append("service_interest")

    # Budget rule, with the explicit "budget unknown" alternative.
    has_budget = bool(draft.get("budget_range"))
    budget_unknown = bool(draft.get("budget_unknown"))
    if not has_budget:
        if not (budget_unknown and user_agrees_to_proceed):
            missing.append("budget_range")

    if missing:
        return ValidationResult(False, reason="missing_required_fields", missing_fields=missing)

    if not user_agrees_to_proceed:
        # All details are known but the user has not signalled they want to start.
        return ValidationResult(False, reason="user_has_not_agreed")

    return ValidationResult(True, reason="ok")


# --------------------------------------------------------------------------- #
# Ticket creation / escalation
# --------------------------------------------------------------------------- #
def validate_ticket_creation(
    *,
    message: str,
    asks_for_human: bool,
    is_frustrated: bool,
    recommended_action: str,
    reason: str,
    confidence: float,
    confidence_threshold: float,
    ticket_created: bool,
) -> ValidationResult:
    """Decide whether an escalation ticket may be opened.

    A ticket is justified only when at least one is true:

    * the user explicitly asks for a human/manager/operator/specialist/support;
    * there is a real complaint/frustration requiring escalation;
    * the request needs custom/enterprise/human review;
    * the planner recommends escalation with high confidence and the backend
      rules agree.

    A ticket is NEVER created for a bare greeting, "I am a new customer",
    "what do you mean?", "I don't remember", "I told you", jokes, ordinary
    confusion, or ordinary swearing without a real support request.
    """
    text = (message or "").lower().strip()

    if ticket_created:
        return ValidationResult(False, reason="ticket_already_exists")

    needs_enterprise = any(h in text for h in _ENTERPRISE_HINTS)
    explicit_signal = asks_for_human or is_frustrated or needs_enterprise

    # Without an explicit escalation signal, a bare greeting / restating /
    # ordinary confusion must never open a ticket — even if the planner asked
    # for one with high confidence. The planner's confidence alone cannot
    # escalate a trivial message.
    if not explicit_signal:
        if text in _GREETING_ONLY or any(hint in text for hint in _TICKET_NEVER_HINTS):
            return ValidationResult(False, reason="not_an_escalation")

    # A high-confidence planner escalation can only carry a *substantive*
    # reason (a complaint or a custom/enterprise need) — never a bare
    # "human_escalation" inferred from small talk.
    high_conf_escalation = (
        recommended_action == "create_ticket"
        and confidence >= confidence_threshold
        and reason in {"complaint", "custom_enterprise"}
    )

    justified = explicit_signal or high_conf_escalation
    if not justified:
        return ValidationResult(False, reason="not_an_escalation")
    return ValidationResult(True, reason="ok")
