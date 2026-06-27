"""Backend-validation and planner-schema tests.

These exercise the new layers added in the LLM-planner refactor:

* the Pydantic planner schema (valid parsing + validation rejection),
* the JSON-repair retry and the controlled planner-error fallback,
* the backend lead/ticket validation rules (success + failure cases),
* and that ``/chat`` only creates leads/tickets when the rules allow it.

Everything runs offline: the LLM is replaced with a small fake that returns
canned strings, and the deterministic mock planner backs the ``/chat`` checks.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent import planner as planner_mod
from app.agent.memory import get_memory
from app.agent.planner import PlannerOutput, parse_decision, validate_planner_output
from app.agent.validation import validate_lead_creation, validate_ticket_creation

_VALID_DECISION = {
    "user_intent": "ask_services",
    "assistant_mode": "answering",
    "extracted_fields": {"service_interest": "Paid ads"},
    "memory_updates": {"facts_to_remember": [], "lead_draft_updates": {}},
    "missing_fields": [],
    "recommended_action": "answer_only",
    "action_payload": {},
    "assistant_reply": "We help with paid ads and SEO.",
    "knowledge_used": False,
    "sources": [],
    "confidence": 0.8,
    "safety_notes": [],
}

_FULL_DRAFT = {
    "name": "Sam",
    "company": "BrightDesk",
    "contact_email": "sam@brightdesk.example",
    "service_interest": "Paid ads",
    "budget_range": "$5k/month",
}


class _FakeLLM:
    """Returns queued responses and counts how many times it was called."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        return "{}"


def _sid(tag: str) -> str:
    return f"val-{tag}-{uuid.uuid4().hex[:6]}"


def _context(message: str) -> dict:
    return {
        "company_profile": {"company_name": "NovaGrowth"},
        "knowledge_context": [],
        "recent_conversation_history": [],
        "session_summary": "",
        "lead_draft": {},
        "ticket_state": {"ticket_created": False, "lead_created": False},
        "available_actions": planner_mod.AVAILABLE_ACTIONS,
        "user_message": message,
    }


# --------------------------------------------------------------------------- #
# Planner schema: valid parsing + validation
# --------------------------------------------------------------------------- #
def test_valid_planner_json_parses_and_validates() -> None:
    data = parse_decision(planner_mod.json.dumps(_VALID_DECISION))
    assert data is not None
    output = validate_planner_output(data)
    assert isinstance(output, PlannerOutput)
    assert output.recommended_action == "answer_only"
    assert output.user_intent == "ask_services"
    assert output.confidence == 0.8


def test_planner_output_rejects_invalid_enum() -> None:
    bad = dict(_VALID_DECISION, recommended_action="delete_everything")
    with pytest.raises(ValidationError):
        validate_planner_output(bad)


def test_planner_output_clamps_confidence() -> None:
    out = validate_planner_output(dict(_VALID_DECISION, confidence=5))
    assert out.confidence == 1.0
    out = validate_planner_output(dict(_VALID_DECISION, confidence=-3))
    assert out.confidence == 0.0


def test_planner_output_ignores_unknown_fields() -> None:
    out = validate_planner_output(dict(_VALID_DECISION, surprise="boom"))
    assert not hasattr(out, "surprise")


# --------------------------------------------------------------------------- #
# JSON repair retry + controlled planner error
# --------------------------------------------------------------------------- #
def test_llm_planner_parses_valid_json_first_try(monkeypatch) -> None:
    fake = _FakeLLM([planner_mod.json.dumps(_VALID_DECISION)])
    monkeypatch.setattr(planner_mod, "get_llm", lambda: fake)
    decision = planner_mod._llm_plan(_context("what do you offer?"), get_memory(), _sid("ok"))
    assert fake.calls == 1
    assert decision.assistant_reply == "We help with paid ads and SEO."
    assert "planner_error" not in decision.safety_notes


def test_llm_planner_repairs_invalid_json_with_one_retry(monkeypatch) -> None:
    fake = _FakeLLM(["sorry, not json here", planner_mod.json.dumps(_VALID_DECISION)])
    monkeypatch.setattr(planner_mod, "get_llm", lambda: fake)
    decision = planner_mod._llm_plan(_context("what do you offer?"), get_memory(), _sid("repair"))
    assert fake.calls == 2  # one repair attempt
    assert decision.assistant_reply == "We help with paid ads and SEO."
    assert "planner_error" not in decision.safety_notes


def test_llm_planner_returns_controlled_error_after_failed_repair(monkeypatch) -> None:
    fake = _FakeLLM(["not json", "still not json"])
    monkeypatch.setattr(planner_mod, "get_llm", lambda: fake)
    decision = planner_mod._llm_plan(_context("???"), get_memory(), _sid("err"))
    assert fake.calls == 2
    assert decision.safety_notes == ["planner_error"]
    assert decision.assistant_reply == ""  # no canned phrase; backend writes the reply


def test_llm_planner_rejects_bad_enum_then_repairs(monkeypatch) -> None:
    bad = planner_mod.json.dumps(dict(_VALID_DECISION, assistant_mode="banana"))
    fake = _FakeLLM([bad, planner_mod.json.dumps(_VALID_DECISION)])
    monkeypatch.setattr(planner_mod, "get_llm", lambda: fake)
    decision = planner_mod._llm_plan(_context("hi"), get_memory(), _sid("enum"))
    assert fake.calls == 2
    assert "planner_error" not in decision.safety_notes


# --------------------------------------------------------------------------- #
# Lead validation: success + failure cases
# --------------------------------------------------------------------------- #
def test_lead_validation_success() -> None:
    r = validate_lead_creation(
        draft=_FULL_DRAFT, lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=True,
    )
    assert r.allowed and r.reason == "ok"


def test_lead_validation_budget_unknown_alternative() -> None:
    draft = {k: v for k, v in _FULL_DRAFT.items() if k != "budget_range"}
    draft["budget_unknown"] = True
    ok = validate_lead_creation(
        draft=draft, lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=True,
    )
    assert ok.allowed
    # ...but only if the user agreed to proceed without a budget.
    no = validate_lead_creation(
        draft=draft, lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=False,
    )
    assert not no.allowed


@pytest.mark.parametrize("drop,reason_field", [
    ("name", "name"),
    ("company", "company"),
    ("contact_email", "contact_email"),
    ("service_interest", "service_interest"),
    ("budget_range", "budget_range"),
])
def test_lead_validation_missing_field_fails(drop, reason_field) -> None:
    draft = {k: v for k, v in _FULL_DRAFT.items() if k != drop}
    r = validate_lead_creation(
        draft=draft, lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=True,
    )
    assert not r.allowed
    assert reason_field in r.missing_fields


def test_lead_validation_invalid_email_fails() -> None:
    r = validate_lead_creation(
        draft=dict(_FULL_DRAFT, contact_email="nope"), lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=True,
    )
    assert not r.allowed and "contact_email" in r.missing_fields


def test_lead_validation_blocks_duplicate() -> None:
    r = validate_lead_creation(
        draft=_FULL_DRAFT, lead_created=True,
        recommended_action="create_lead", user_agrees_to_proceed=True,
    )
    assert not r.allowed and r.reason == "lead_already_exists"


def test_lead_validation_requires_recommendation() -> None:
    r = validate_lead_creation(
        draft=_FULL_DRAFT, lead_created=False,
        recommended_action="answer_only", user_agrees_to_proceed=True,
    )
    assert not r.allowed and r.reason == "action_not_recommended"


def test_lead_validation_requires_user_agreement() -> None:
    r = validate_lead_creation(
        draft=_FULL_DRAFT, lead_created=False,
        recommended_action="create_lead", user_agrees_to_proceed=False,
    )
    assert not r.allowed and r.reason == "user_has_not_agreed"


# --------------------------------------------------------------------------- #
# Ticket validation: success + failure cases
# --------------------------------------------------------------------------- #
def _ticket(**over):
    base = dict(
        message="", asks_for_human=False, is_frustrated=False,
        recommended_action="create_ticket", reason="human_escalation",
        confidence=0.2, confidence_threshold=0.45, ticket_created=False,
    )
    base.update(over)
    return validate_ticket_creation(**base)


def test_ticket_validation_success_human_request() -> None:
    assert _ticket(message="I want a human manager", asks_for_human=True).allowed


def test_ticket_validation_success_complaint() -> None:
    assert _ticket(message="this is terrible", is_frustrated=True).allowed


def test_ticket_validation_success_enterprise() -> None:
    assert _ticket(message="we need a custom enterprise workflow", reason="custom_enterprise").allowed


def test_ticket_validation_success_high_confidence() -> None:
    assert _ticket(message="please escalate", reason="complaint", confidence=0.9).allowed


@pytest.mark.parametrize("msg", [
    "hello",
    "I am a new customer",
    "what do you mean?",
    "I don't remember",
    "I told you already",
])
def test_ticket_validation_rejects_non_escalations(msg) -> None:
    assert not _ticket(message=msg, confidence=0.9).allowed


def test_ticket_validation_blocks_duplicate() -> None:
    r = _ticket(message="human please", asks_for_human=True, ticket_created=True)
    assert not r.allowed and r.reason == "ticket_already_exists"


# --------------------------------------------------------------------------- #
# /chat end-to-end guards (deterministic mock planner)
# --------------------------------------------------------------------------- #
def _chat(client: TestClient, sid: str, msg: str):
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def test_chat_casual_message_creates_nothing(client: TestClient) -> None:
    data = _chat(client, _sid("casual"), "haha just kidding, hello again")
    assert data["lead_created"] is False
    assert data["ticket_created"] is False
    assert data["action_executed"] is False


def test_chat_exposes_validation_metadata(client: TestClient) -> None:
    data = _chat(client, _sid("meta"), "What services do you offer?")
    assert "planner_decision" in data
    assert "validation" in data
    assert "action_executed" in data


def test_chat_creates_exactly_one_lead_when_complete(client: TestClient) -> None:
    sid = _sid("lead")
    _chat(client, sid, "I need help with paid ads for my SaaS")
    _chat(client, sid, "Collect details")
    _chat(client, sid, "Company is BrightDesk, budget around $5k/month")
    created = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert created["lead_created"] is True
    assert created["lead_id"] is not None
    assert created["action_executed"] is True
    again = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert again["lead_id"] == created["lead_id"]


def test_chat_creates_ticket_only_on_valid_escalation(client: TestClient) -> None:
    no = _chat(client, _sid("noesc"), "hello there")
    assert no["ticket_created"] is False
    yes = _chat(client, _sid("esc"), "I need to speak to a human manager")
    assert yes["ticket_created"] is True
    assert yes["ticket_id"] is not None
    assert yes["action_executed"] is True
