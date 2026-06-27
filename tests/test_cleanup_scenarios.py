"""Post-cleanup behavioural scenarios.

These lock in the product rules after removing scripted demo behaviour: casual
and abusive messages never create a lead or ticket, confused users are
remembered (not re-interrogated), a lead is created only once all details are
present, explicit human requests escalate, and knowledge questions are answered
with tracked sources. All run offline against the deterministic mock planner.
"""
import uuid

import pytest
from fastapi.testclient import TestClient


def _chat(client: TestClient, sid: str, msg: str):
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def _sid(tag: str) -> str:
    return f"clean-{tag}-{uuid.uuid4().hex[:6]}"


# --------------------------------------------------------------------------- #
# Casual / meta / abusive messages create nothing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("msg", [
    "Hello",
    "SAY HELLO TO ME",
    "Another one",
    "What do you mean?",
    "EXPLAIN WHAT DO YOU MEAN",
    "FUCKING IDIOT",
])
def test_casual_and_abusive_messages_create_nothing(client: TestClient, msg) -> None:
    data = _chat(client, _sid("casual"), msg)
    assert data["lead_created"] is False
    assert data["ticket_created"] is False
    assert data["action_executed"] is False
    assert data["answer"]  # a natural reply is always returned


def test_repeated_confusion_does_not_escalate(client: TestClient) -> None:
    """Repeated confusion/venting must never open a ticket or loop a menu."""
    sid = _sid("repeat")
    seen = []
    for msg in ["What do you mean?", "EXPLAIN WHAT DO YOU MEAN", "FUCKING IDIOT"]:
        data = _chat(client, sid, msg)
        assert data["ticket_created"] is False
        assert data["lead_created"] is False
        seen.append(data["answer"])
    # The assistant should not repeat the exact same fallback every turn.
    assert len(set(seen)) > 1


# --------------------------------------------------------------------------- #
# Confused user is remembered, not re-interrogated, and never auto-converted
# --------------------------------------------------------------------------- #
def test_confused_user_remembers_company_no_lead_no_ticket(client: TestClient) -> None:
    sid = _sid("confused")
    _chat(client, sid, "Hello I need help with marketing")
    _chat(client, sid, "I don't know. Help me with that")
    _chat(client, sid, "Help starting a project please")
    _chat(client, sid, "I want paid ads for my SaaS")
    _chat(client, sid, "I don't remember")
    r = _chat(client, sid, "Oh sorry, company is FalkoTeam")
    assert r["lead_draft"].get("company") == "FalkoTeam"
    final = _chat(client, sid, "FalkoTeam, I told you")
    # Memory is preserved across turns.
    assert final["lead_draft"].get("company") == "FalkoTeam"
    assert final["lead_draft"].get("service_interest")
    # No conversion without name / email / budget, and no escalation.
    assert final["lead_created"] is False
    assert final["ticket_created"] is False


# --------------------------------------------------------------------------- #
# Lead is created only after the final message, exactly once
# --------------------------------------------------------------------------- #
def test_lead_created_only_after_final_message(client: TestClient) -> None:
    sid = _sid("lead")
    _chat(client, sid, "I want to start a project")
    _chat(client, sid, "Paid ads for my SaaS")
    partial = _chat(client, sid, "Company is BrightDesk, budget around $5k/month")
    assert partial["lead_created"] is False  # name + email still missing

    created = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert created["lead_created"] is True
    assert created["lead_id"] is not None
    assert created["action_executed"] is True

    draft = created["lead_draft"]
    assert draft.get("company") == "BrightDesk"
    assert draft.get("name") == "Sam"
    assert draft.get("contact_email") == "sam@brightdesk.example"
    assert "paid" in (draft.get("service_interest", "").lower())
    assert draft.get("product_type") == "SaaS"
    assert "5k" in (draft.get("budget_range", "") or "")

    # Exactly one lead — repeating details does not duplicate it.
    again = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert again["lead_id"] == created["lead_id"]
    leads = client.get("/crm/leads").json()
    assert len([x for x in leads if x["id"] == created["lead_id"]]) == 1


# --------------------------------------------------------------------------- #
# Explicit human request escalates (and only then)
# --------------------------------------------------------------------------- #
def test_human_request_escalates_after_backend_confirms(client: TestClient) -> None:
    data = _chat(client, _sid("human"), "I need a human manager")
    assert data["ticket_created"] is True
    assert data["ticket_id"] is not None
    assert data["action_executed"] is True


# --------------------------------------------------------------------------- #
# RAG questions answered with tracked sources (not raw chunks)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("msg", [
    "What services do you provide?",
    "What pricing packages are available?",
])
def test_knowledge_questions_track_sources(client: TestClient, msg) -> None:
    data = _chat(client, _sid("rag"), msg)
    assert data["knowledge_used"] is True
    assert data["sources"]
    assert data["lead_created"] is False
    assert data["ticket_created"] is False
