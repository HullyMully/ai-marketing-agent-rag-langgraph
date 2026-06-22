"""Ticket creation / retrieval tests."""
from fastapi.testclient import TestClient


def test_create_get_ticket(client: TestClient) -> None:
    payload = {
        "user_id": "user-123",
        "reason": "support_request",
        "summary": "Cannot access dashboard.",
        "priority": "normal",
    }
    resp = client.post("/tickets", json=payload)
    assert resp.status_code == 201
    ticket = resp.json()
    assert ticket["status"] == "open"

    fetched = client.get(f"/tickets/{ticket['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == ticket["id"]


def test_get_missing_ticket_returns_404(client: TestClient) -> None:
    resp = client.get("/tickets/999999")
    assert resp.status_code == 404
