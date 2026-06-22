"""Chat endpoint + agent behaviour tests (offline / mock mode)."""
import uuid

from fastapi.testclient import TestClient


def _chat(client: TestClient, session_id: str, message: str, user_id: str | None = None):
    resp = client.post(
        "/chat",
        json={"session_id": session_id, "user_message": message, "user_id": user_id},
    )
    assert resp.status_code == 200
    return resp.json()


def test_chat_basic_response(client: TestClient) -> None:
    data = _chat(client, "sess-basic", "What services do you offer?")
    assert data["answer"]
    assert data["intent"] in {"service_question", "general_question"}
    assert data["escalated"] is False


def test_chat_pricing_uses_rag(client: TestClient) -> None:
    data = _chat(client, "sess-pricing", "How much does the Growth package cost?")
    assert data["intent"] == "pricing_question"
    # RAG should run and surface knowledge-base sources for the answer.
    assert data["sources"], "expected retrieved sources for a pricing question"
    assert data["answer"]


def test_chat_escalation_when_user_asks_for_human(client: TestClient) -> None:
    data = _chat(client, "sess-esc", "I want to speak to a human manager please.")
    assert data["intent"] == "human_escalation"
    assert data["escalated"] is True
    assert data["created_ticket_id"] is not None


def test_chat_fallback_unknown_intent(client: TestClient) -> None:
    data = _chat(client, "sess-unknown", "asdf")
    # Very short gibberish -> low confidence -> escalation fallback.
    assert data["intent"] in {"unknown", "general_question"}


def test_chat_lead_creation_with_memory(client: TestClient) -> None:
    session = f"sess-lead-{uuid.uuid4().hex[:6]}"
    # First turn: intent to become a client, but missing contact details.
    first = _chat(client, session, "I want to run Google Ads for my store.")
    assert first["intent"] == "create_lead"
    assert first["created_lead_id"] is None  # needs follow-up info

    # Second turn: provide details; agent should remember intent and create lead.
    second = _chat(
        client,
        session,
        "My name is Sam Carter and my email is sam@store.example.",
    )
    assert second["created_lead_id"] is not None
    assert second["action_taken"] == "created_lead"
