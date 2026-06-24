"""Multi-turn conversation regression tests.

Covers a willing prospect who progresses through uncertainty, an exploration
detour and a correction, ending in exactly one lead — with no repeated fallback
messages. The confused/joking/refusal conversation lives in
``test_dialogue_policy.py``.
"""
import uuid

from fastapi.testclient import TestClient


def _chat(client: TestClient, sid: str, msg: str):
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def test_full_natural_conversation(client: TestClient) -> None:
    sid = f"conv-{uuid.uuid4().hex[:6]}"
    answers = []

    r = _chat(client, sid, "Hello I need help with marketing")
    answers.append(r["answer"])
    assert r["lead_created"] is False and r["ticket_created"] is False
    assert r["action"] != "asked_clarification"

    # Confusion early on -> exploration, never a forced lead question.
    r = _chat(client, sid, "I don't know. Help me with that")
    answers.append(r["answer"])
    assert r["lead_created"] is False and r["ticket_created"] is False
    assert r["mode"] == "exploring"

    # A clear request re-engages qualification.
    r = _chat(client, sid, "Help starting a project please")
    answers.append(r["answer"])
    assert r["lead_created"] is False
    assert r["mode"] == "qualifying"

    r = _chat(client, sid, "I want to paid ads for my saas")
    assert "paid" in (r["lead_draft"].get("service_interest", "").lower())
    assert r["lead_draft"].get("product_type") == "SaaS"
    assert r["lead_created"] is False

    # Can't remember -> exploration, draft is NOT reset and no repeated question.
    r = _chat(client, sid, "I don't remember")
    answers.append(r["answer"])
    assert r["lead_draft"].get("service_interest")
    assert r["mode"] == "exploring"

    r = _chat(client, sid, "Oh sorry, I remember! My company's name is FalkoTeam")
    assert r["lead_draft"].get("company") == "FalkoTeam"
    assert r["mode"] == "qualifying"

    r = _chat(client, sid, "FalkoTeam, I told u")
    assert r["lead_draft"].get("company") == "FalkoTeam"  # acknowledged, not reset
    assert r["lead_created"] is False

    r = _chat(client, sid, "My name is David and email is david@example.com")
    assert r["lead_draft"].get("name") == "David"
    assert r["lead_draft"].get("contact_email") == "david@example.com"
    assert r["lead_created"] is False  # budget still missing

    r = _chat(client, sid, "Budget is around $3k/month")
    assert r["lead_created"] is True and r["lead_id"] is not None
    lead_id = r["lead_id"]

    # Duplicate guard: repeating details must not create a second lead.
    again = _chat(client, sid, "My name is David and email is david@example.com")
    assert again["lead_id"] == lead_id
    assert again["action"] == "lead_already_exists"


def test_willing_lead_terse_flow(client: TestClient) -> None:
    """A cooperative user giving terse answers still produces one lead."""
    sid = f"conv-{uuid.uuid4().hex[:6]}"
    _chat(client, sid, "Hello, I need help with marketing")
    _chat(client, sid, "Paid ads for my SaaS")
    partial = _chat(client, sid, "BrightDesk, around $5k/month")
    assert partial["lead_draft"].get("company") == "BrightDesk"
    assert partial["lead_created"] is False
    created = _chat(client, sid, "Sam, sam@brightdesk.example")
    assert created["lead_created"] is True and created["lead_id"] is not None


def test_human_request_creates_ticket(client: TestClient) -> None:
    r = _chat(client, f"esc-{uuid.uuid4().hex[:6]}", "I need a human manager")
    assert r["ticket_created"] is True and r["ticket_id"] is not None


def test_service_question_uses_source(client: TestClient) -> None:
    r = _chat(client, f"svc-{uuid.uuid4().hex[:6]}", "What services do you provide?")
    assert r["sources"]


def test_pricing_question_uses_source(client: TestClient) -> None:
    r = _chat(client, f"prc-{uuid.uuid4().hex[:6]}", "What pricing packages are available?")
    assert r["sources"]
