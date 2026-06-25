"""Tests for the local web demo pages and static assets."""
from fastapi.testclient import TestClient

from app import company as company_mod


def test_landing_page_ok(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Generic, configurable product name — not a hardcoded demo company.
    assert "AI Customer Assistant" in resp.text


def test_landing_page_has_no_hardcoded_company(client: TestClient) -> None:
    # The old demo company must not leak into the shipped UI.
    resp = client.get("/")
    assert "NovaGrowth" not in resp.text


def test_demo_page_ok(client: TestClient) -> None:
    resp = client.get("/demo")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/static/styles.css" in resp.text
    assert "/static/demo.js" in resp.text


def test_demo_page_has_no_hardcoded_company(client: TestClient) -> None:
    resp = client.get("/demo")
    assert "NovaGrowth" not in resp.text


def test_demo_page_has_suggested_prompts(client: TestClient) -> None:
    resp = client.get("/demo")
    assert "Suggested prompts" in resp.text
    # Suggested prompt buttons send normal messages to /chat.
    assert 'data-prompt="What services do you provide?"' in resp.text
    assert 'data-prompt="Can I talk to a human?"' in resp.text
    # The right panel is the real conversation-state view.
    assert "Conversation state" in resp.text


def test_api_overview_page_ok(client: TestClient) -> None:
    resp = client.get("/api-overview")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/chat" in resp.text


def test_metrics_page_ok(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Local workspace metrics" in resp.text


def test_admin_page_ok(client: TestClient) -> None:
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Leads and customer requests" in resp.text
    assert "Company profile" in resp.text
    assert "Knowledge base" in resp.text
    assert "Human inbox" in resp.text
    assert "CRM sync" in resp.text
    assert "Audit log" in resp.text
    assert 'name="company_name"' in resp.text
    assert "/static/admin.js" in resp.text


def test_company_profile_api_can_update_local_profile(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(company_mod, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(company_mod, "_profile", None)
    payload = {
        "company_name": "Panel Studio",
        "company_domain": "panel.example",
        "company_description": "Panel-managed profile",
        "company_contact_email": "hello@panel.example",
        "assistant_name": "Panel Assistant",
        "escalation_target": "account manager",
        "business_industry": "SaaS",
    }

    saved = client.put("/config/profile", json=payload)

    assert saved.status_code == 200
    body = saved.json()
    assert body["company_name"] == "Panel Studio"
    assert body["brand_label"] == "Panel Studio Assistant"
    assert (tmp_path / "company.local.json").exists()

    loaded = client.get("/config/profile")
    assert loaded.status_code == 200
    assert loaded.json()["assistant_name"] == "Panel Assistant"


def test_static_css_loads(client: TestClient) -> None:
    resp = client.get("/static/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_js_loads(client: TestClient) -> None:
    resp = client.get("/static/demo.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_static_admin_js_loads(client: TestClient) -> None:
    resp = client.get("/static/admin.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
