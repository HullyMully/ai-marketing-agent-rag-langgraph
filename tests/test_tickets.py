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


def test_update_ticket_and_add_internal_note(client: TestClient) -> None:
    created = client.post(
        "/tickets",
        json={
            "user_id": "user-456",
            "reason": "human_escalation",
            "summary": "Needs pricing approval from a manager.",
            "priority": "normal",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    updated = client.patch(
        f"/tickets/{ticket_id}",
        json={"status": "in_progress", "priority": "high", "assignee": "Nina"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["assignee"] == "Nina"

    note = client.post(
        f"/tickets/{ticket_id}/notes",
        json={"author": "Nina", "body": "Asked sales to prepare a proposal."},
    )
    assert note.status_code == 201
    assert note.json()["body"] == "Asked sales to prepare a proposal."

    notes = client.get(f"/tickets/{ticket_id}/notes")
    assert notes.status_code == 200
    assert any(row["author"] == "Nina" for row in notes.json())

    audit = client.get("/audit/events")
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()}
    assert {"ticket.updated", "ticket_note.created"}.issubset(actions)


def test_get_missing_ticket_returns_404(client: TestClient) -> None:
    resp = client.get("/tickets/999999")
    assert resp.status_code == 404
