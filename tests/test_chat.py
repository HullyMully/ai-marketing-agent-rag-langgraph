"""Chat endpoint basics (offline / mock mode)."""
import uuid

from fastapi.testclient import TestClient


def _chat(client: TestClient, session_id: str, message: str):
    resp = client.post(
        "/chat", json={"session_id": session_id, "user_message": message},
    )
    assert resp.status_code == 200
    return resp.json()


def test_chat_services_question(client: TestClient) -> None:
    data = _chat(client, "sess-svc", "What services do you offer?")
    assert data["answer"]
    assert data["intent"] == "service_question"
    assert data["escalated"] is False


def test_chat_pricing_uses_rag(client: TestClient) -> None:
    data = _chat(client, "sess-price", "What pricing packages are available?")
    assert data["intent"] == "pricing_question"
    assert data["sources"]


def test_chat_human_request_creates_ticket(client: TestClient) -> None:
    data = _chat(client, "sess-human", "I want to speak to a human manager please.")
    assert data["intent"] == "human_escalation"
    assert data["ticket_created"] is True
    assert data["ticket_id"] is not None


def test_chat_unknown_asks_clarification(client: TestClient) -> None:
    data = _chat(client, f"sess-unk-{uuid.uuid4().hex[:6]}", "asdf qwerty zxcv")
    assert data["action"] == "asked_clarification"
    assert data["ticket_created"] is False
    assert data["ticket_id"] is None
