"""Regression tests for the natural-dialogue policy.

These reproduce the previously-broken conversation where the assistant repeated
the same qualification question and ignored greetings, jokes, confusion and
frustration. The assistant should now acknowledge social messages, adapt, switch
to exploration when the user can't/won't share details, pause qualification after
repeated refusal, and never create a lead or ticket from this conversation.
"""
import uuid

from fastapi.testclient import TestClient


def _chat(client: TestClient, sid: str, msg: str):
    resp = client.post("/chat", json={"session_id": sid, "user_message": msg})
    assert resp.status_code == 200
    return resp.json()


def _sid() -> str:
    return f"dlg-{uuid.uuid4().hex[:6]}"


def test_hello_is_social_no_forced_qualification(client: TestClient) -> None:
    r = _chat(client, _sid(), "Hello")
    assert r["lead_created"] is False and r["ticket_created"] is False
    assert r["action"] == "greeted"
    assert r["mode"] == "answering"
    # No qualification pressure on a plain hello.
    lower = r["answer"].lower()
    assert "budget" not in lower and "company" not in lower


def test_repeated_hello_does_not_repeat_response(client: TestClient) -> None:
    sid = _sid()
    a = _chat(client, sid, "Hello")["answer"]
    b = _chat(client, sid, "Hello!")["answer"]
    assert a != b  # the assistant varies its greeting


def test_says_just_hello_is_acknowledged(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "Hello")
    _chat(client, sid, "Hello!")
    r = _chat(client, sid, "What do you mean? I wanna to hello to you")
    assert r["action"] == "greeted"
    assert "hello" in r["answer"].lower()
    assert r["lead_created"] is False


def test_bare_service_asks_explore_vs_request(client: TestClient) -> None:
    sid = _sid()
    r = _chat(client, sid, "seo")
    assert "SEO" in (r["lead_draft"].get("service_interest", "") or "")
    assert r["action"] == "clarifying_direction"
    assert r["mode"] == "exploring"
    assert r["lead_created"] is False


def test_joking_correction_updates_to_paid_ads_saas(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "seo")
    r = _chat(client, sid, "Hahahah I'm joking. I need paid ads for my saas")
    assert "paid" in r["lead_draft"].get("service_interest", "").lower()
    assert r["lead_draft"].get("product_type") == "SaaS"
    assert r["lead_created"] is False


def test_additive_service_combines(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "seo")
    _chat(client, sid, "Hahahah I'm joking. I need paid ads for my saas")
    r = _chat(client, sid, "and seo")
    service = r["lead_draft"].get("service_interest", "").lower()
    assert "paid" in service and "seo" in service  # combined, not replaced
    assert r["lead_created"] is False


def test_wants_guidance_gives_help_not_company_budget(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "I need paid ads for my saas")
    r = _chat(client, sid, "Help me with that")
    assert r["mode"] in ("exploring",)
    assert r["action"] == "exploring"
    lower = r["answer"].lower()
    assert "budget" not in lower and "company name" not in lower


def test_refusal_enters_exploration_no_lead(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "I need paid ads for my saas")
    r = _chat(client, sid, "No(")
    assert r["exploration_mode"] is True
    assert r["lead_created"] is False


def test_cannot_remember_does_not_repeat_company_budget(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "I need paid ads for my saas")
    first = _chat(client, sid, "Help me with that")["answer"]
    r = _chat(client, sid, "I don't remember")
    # Service interest is retained, and we don't re-ask company/budget.
    assert "paid" in r["lead_draft"].get("service_interest", "").lower()
    assert "budget" not in r["answer"].lower()
    assert r["answer"] != first  # progresses rather than repeating


def test_repeated_refusal_pauses_qualification(client: TestClient) -> None:
    sid = _sid()
    _chat(client, sid, "I need paid ads for my saas")
    _chat(client, sid, "No(")
    _chat(client, sid, "I don't remember")
    _chat(client, sid, "I FORGOT")
    r = _chat(client, sid, "NO")
    assert r["qualification_paused"] is True
    assert r["mode"] == "paused"
    assert "won't ask" in r["answer"].lower() or "pause" in r["answer"].lower()


def test_full_broken_conversation_creates_no_lead_or_ticket(client: TestClient) -> None:
    sid = _sid()
    script = [
        "Hello",
        "Hello!",
        "What do you mean? I wanna to hello to you",
        "seo",
        "Hahahah I'm joking. I need paid ads for my saas",
        "and seo",
        "Help me with that",
        "No(",
        "I don't remember",
        "I FORGOT",
        "NO",
    ]
    answers = []
    for msg in script:
        r = _chat(client, sid, msg)
        assert r["lead_created"] is False, f"lead created at: {msg}"
        assert r["ticket_created"] is False, f"ticket created at: {msg}"
        answers.append(r["answer"])
    # Final state: qualification paused, interests still remembered.
    assert r["qualification_paused"] is True
    interests = " ".join(r["known_interests"]).lower()
    assert "paid ads" in interests and "seo" in interests
    # No two consecutive answers are identical (no robotic repetition).
    for a, b in zip(answers, answers[1:]):
        assert a != b
