"""Planner + backend-validation tests.

The LLM planner only *recommends* actions; the backend decides whether they run.
These tests use canned planner decisions (no API calls) to prove the backend
validates lead/ticket creation safely, plus a few end-to-end checks with the
deterministic mock planner.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.agent import graph as graph_mod
from app.agent import planner as planner_mod
from app.agent.memory import get_memory
from app.agent.planner import PlannerDecision, parse_decision


def _chat(client: TestClient, sid: str, msg: str):
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def _sid(tag: str) -> str:
    return f"plan-{tag}-{uuid.uuid4().hex[:6]}"


def _canned(decision: PlannerDecision):
    def _plan(context, memory=None, session=None):
        return decision
    return _plan


# --------------------------------------------------------------------------- #
# Robust JSON parsing
# --------------------------------------------------------------------------- #
def test_parse_decision_handles_plain_json() -> None:
    assert parse_decision('{"a": 1}') == {"a": 1}


def test_parse_decision_handles_fenced_and_trailing_text() -> None:
    raw = "Sure!\n```json\n{\"recommended_action\": \"answer_only\",}\n```\nthanks"
    data = parse_decision(raw)
    assert data and data["recommended_action"] == "answer_only"


def test_parse_decision_returns_none_on_garbage() -> None:
    assert parse_decision("not json at all") is None


# --------------------------------------------------------------------------- #
# Backend validation of LLM recommendations
# --------------------------------------------------------------------------- #
def test_create_lead_blocked_when_email_missing(client: TestClient, monkeypatch) -> None:
    sid = _sid("noemail")
    mem = get_memory()
    mem.update_draft(sid, {
        "name": "Sam", "company": "BrightDesk",
        "service_interest": "Paid ads", "budget_range": "$5k/month",
    })
    mem.set_flag(sid, "qualification_active", True)

    decision = PlannerDecision(recommended_action="create_lead", assistant_reply="")
    monkeypatch.setattr(planner_mod, "plan", _canned(decision))

    data = _chat(client, sid, "go ahead")
    assert data["lead_created"] is False
    assert data["ticket_created"] is False


def test_create_lead_succeeds_with_all_fields(client: TestClient, monkeypatch) -> None:
    sid = _sid("ok")
    mem = get_memory()
    mem.update_draft(sid, {
        "name": "Sam", "company": "BrightDesk", "contact_email": "sam@brightdesk.example",
        "service_interest": "Paid ads", "budget_range": "$5k/month",
    })
    mem.set_flag(sid, "qualification_active", True)

    monkeypatch.setattr(planner_mod, "plan",
                        _canned(PlannerDecision(recommended_action="create_lead")))
    data = _chat(client, sid, "go ahead")
    assert data["lead_created"] is True and data["lead_id"] is not None


def test_duplicate_create_lead_recommendation_makes_one_lead(client: TestClient, monkeypatch) -> None:
    sid = _sid("dup")
    mem = get_memory()
    mem.update_draft(sid, {
        "name": "Sam", "company": "BrightDesk", "contact_email": "sam@brightdesk.example",
        "service_interest": "Paid ads", "budget_range": "$5k/month",
    })
    mem.set_flag(sid, "qualification_active", True)
    monkeypatch.setattr(planner_mod, "plan",
                        _canned(PlannerDecision(recommended_action="create_lead")))

    first = _chat(client, sid, "go ahead")
    second = _chat(client, sid, "go ahead")
    assert first["lead_created"] is True
    lead_id = first["lead_id"]
    # No duplicate lead created in the CRM for this company.
    leads = client.get("/crm/leads").json()
    assert len([x for x in leads if x["id"] == lead_id]) == 1


def test_ticket_rejected_for_greeting(client: TestClient, monkeypatch) -> None:
    sid = _sid("badticket")
    decision = PlannerDecision(
        recommended_action="create_ticket", confidence=0.2,
        action_payload={"reason": "human_escalation"}, assistant_reply="Hi!",
    )
    monkeypatch.setattr(planner_mod, "plan", _canned(decision))
    data = _chat(client, sid, "hello")
    assert data["ticket_created"] is False
    assert data["ticket_id"] is None


def test_human_request_creates_ticket(client: TestClient) -> None:
    data = _chat(client, _sid("human"), "I need to talk to a human manager")
    assert data["ticket_created"] is True and data["ticket_id"] is not None


# --------------------------------------------------------------------------- #
# End-to-end with the deterministic mock planner
# --------------------------------------------------------------------------- #
def test_service_question_returns_sources(client: TestClient) -> None:
    data = _chat(client, _sid("svc"), "What services do you provide?")
    assert data["knowledge_used"] is True
    assert data["sources"]


def test_meta_question_no_lead_or_ticket(client: TestClient) -> None:
    data = _chat(client, _sid("meta"), "What did I tell you so far?")
    assert data["recommended_action"] == "answer_only"
    assert data["lead_created"] is False and data["ticket_created"] is False


def test_confused_user_no_lead_or_ticket(client: TestClient) -> None:
    sid = _sid("confused")
    data = _chat(client, sid, "I don't know what I want, can you suggest?")
    assert data["lead_created"] is False and data["ticket_created"] is False
    assert data["recommended_action"] in ("ask_clarifying_question", "answer_only")


def test_natural_flow_creates_one_lead_after_final_message(client: TestClient) -> None:
    sid = _sid("flow")
    _chat(client, sid, "Hello")
    _chat(client, sid, "I need help with paid ads for my SaaS")
    _chat(client, sid, "Collect details")
    _chat(client, sid, "Company is BrightDesk")
    partial = _chat(client, sid, "Budget is around $5k/month")
    assert partial["lead_created"] is False  # name + email still missing
    created = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert created["lead_created"] is True and created["lead_id"] is not None
    again = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert again["lead_id"] == created["lead_id"]


# --------------------------------------------------------------------------- #
# The user-facing reply is generated after planner + validation
# --------------------------------------------------------------------------- #
def test_assistant_reply_is_not_raw_planner_draft(client: TestClient, monkeypatch) -> None:
    """The planner can provide a draft, but the final reply layer owns the text."""
    sid = _sid("passthrough")
    decision = PlannerDecision(
        recommended_action="answer_only",
        user_intent="ask_services",
        assistant_reply="We focus on paid ads, SEO and analytics.",
        confidence=0.77,
    )
    monkeypatch.setattr(planner_mod, "plan", _canned(decision))

    data = _chat(client, sid, "what do you do?")
    assert data["answer"]
    assert data["answer"] != "We focus on paid ads, SEO and analytics."
    assert data["recommended_action"] == "answer_only"
    assert data["planner_decision"]["user_intent"] == "ask_services"
    assert data["lead_created"] is False and data["ticket_created"] is False
    assert data["action_executed"] is False


def test_real_mode_final_reply_is_authored_by_llm(client: TestClient, monkeypatch) -> None:
    """In product mode, the final answer comes from the LLM prompt, not mock text."""
    sid = _sid("real-final")
    prompts: list[str] = []

    class FakeLLM:
        def complete(self, prompt: str) -> str:
            prompts.append(prompt)
            return "LLM-authored reply from the full conversation context."

    monkeypatch.setattr(graph_mod.settings, "mock_llm", False)
    monkeypatch.setattr(graph_mod, "get_llm", lambda: FakeLLM())
    decision = PlannerDecision(
        conversation_target="assistant_product",
        context_relation="asks_meta_question",
        recommended_action="answer_only",
        user_intent="meta_question",
        assistant_reply="planner draft should not be returned",
    )
    monkeypatch.setattr(planner_mod, "plan", _canned(decision))

    data = _chat(client, sid, "SPEAK ENGLISH PLEASE")

    assert data["answer"] == "LLM-authored reply from the full conversation context."
    assert data["llm_runtime_mode"] == "llm"
    assert data["mock_llm"] is False
    assert prompts
    assert "Relevant company knowledge" in prompts[-1]
    assert "Conversation so far" in prompts[-1]
    assert "Reply in English" in prompts[-1]
    assert "planner draft should not be returned" in prompts[-1]


def test_real_mode_llm_failure_does_not_use_mock_templates(client: TestClient, monkeypatch) -> None:
    """If product LLM is unavailable, expose that instead of pretending with mock replies."""
    sid = _sid("real-fail")

    class FailingLLM:
        def complete(self, prompt: str) -> str:
            raise RuntimeError("provider down")

    monkeypatch.setattr(graph_mod.settings, "mock_llm", False)
    monkeypatch.setattr(graph_mod, "get_llm", lambda: FailingLLM())
    monkeypatch.setattr(
        planner_mod,
        "plan",
        _canned(PlannerDecision(recommended_action="answer_only", user_intent="unclear")),
    )

    data = _chat(client, sid, "heelllllo")

    assert "language model is unavailable" in data["answer"].lower()
    assert "tell me a little more" not in data["answer"].lower()
    assert "what should i help with specifically" not in data["answer"].lower()
    assert data["llm_runtime_mode"] == "llm"
    assert data["mock_llm"] is False
