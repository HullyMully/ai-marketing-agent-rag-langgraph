"""Mock CRM lead creation tests."""
from fastapi.testclient import TestClient


def test_create_and_list_lead(client: TestClient) -> None:
    payload = {
        "name": "Jamie Lee",
        "contact": "jamie@acme.example",
        "company": "Acme Co",
        "service_interest": "SEO",
        "budget_range": "$1,500-$5,000",
        "message": "Interested in SEO.",
    }
    resp = client.post("/crm/leads", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] > 0
    assert created["name"] == "Jamie Lee"
    assert created["status"] == "new"

    listed = client.get("/crm/leads")
    assert listed.status_code == 200
    assert any(lead["id"] == created["id"] for lead in listed.json())
