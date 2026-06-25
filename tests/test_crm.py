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


def test_crm_integration_records_dispatch_attempts(client: TestClient) -> None:
    integration = client.put(
        "/crm/integration",
        json={
            "provider": "hubspot",
            "enabled": True,
            "webhook_url": None,
            "api_key_env": "HUBSPOT_API_KEY",
            "pipeline_name": "Inbound SaaS leads",
        },
    )
    assert integration.status_code == 200
    assert integration.json()["provider"] == "hubspot"
    assert integration.json()["enabled"] is True

    created = client.post(
        "/crm/leads",
        json={
            "name": "Mira Stone",
            "contact": "mira@example.com",
            "company": "Stone SaaS",
            "service_interest": "Paid ads",
        },
    )
    assert created.status_code == 201
    lead_id = created.json()["id"]

    dispatches = client.get("/crm/dispatches")
    assert dispatches.status_code == 200
    assert any(
        row["lead_id"] == lead_id
        and row["provider"] == "hubspot"
        and row["status"] == "skipped"
        for row in dispatches.json()
    )


def test_crm_integration_updates_are_audited(client: TestClient) -> None:
    resp = client.put(
        "/crm/integration",
        json={"provider": "local", "enabled": False},
    )
    assert resp.status_code == 200

    audit = client.get("/audit/events")
    assert audit.status_code == 200
    assert any(event["action"] == "crm_integration.updated" for event in audit.json())
