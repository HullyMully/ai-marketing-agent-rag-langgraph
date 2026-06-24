"""Lead-qualification flow and routing regression tests (offline / mock mode)."""
import uuid

from fastapi.testclient import TestClient


def _chat(client: TestClient, session_id: str, message: str):
    resp = client.post(
        "/chat", json={"session_id": session_id, "user_message": message},
    )
    assert resp.status_code == 200
    return resp.json()


def _sid(tag: str) -> str:
    return f"flow-{tag}-{uuid.uuid4().hex[:6]}"


def test_greeting_new_customer_asks_service_no_lead_or_ticket(client: TestClient) -> None:
    data = _chat(client, _sid("greet"), "Hello I am a new customer")
    assert data["lead_created"] is False
    assert data["ticket_created"] is False
    assert "service_interest" in data["missing_fields"]


def test_saas_ads_sets_service_and_asks_company_budget(client: TestClient) -> None:
    sid = _sid("ads")
    _chat(client, sid, "Hello I am a new customer")
    data = _chat(client, sid, "I need help with SaaS ads")
    assert "paid" in (data["lead_draft"].get("service_interest", "").lower())
    assert data["lead_created"] is False
    assert "company" in data["missing_fields"]
    assert "budget_range" in data["missing_fields"]


def test_company_budget_does_not_create_lead_without_name_email(client: TestClient) -> None:
    sid = _sid("cb")
    _chat(client, sid, "I need help with SaaS ads")
    data = _chat(client, sid, "Company is BrightDesk, budget around $5k/month")
    assert data["lead_draft"].get("company") == "BrightDesk"
    assert data["lead_draft"].get("budget_range") == "$5k/month"
    assert data["lead_created"] is False
    assert "name" in data["missing_fields"]
    assert "contact_email" in data["missing_fields"]


def test_full_flow_creates_one_lead_no_duplicate(client: TestClient) -> None:
    sid = _sid("full")
    _chat(client, sid, "Hello I am a new customer")
    _chat(client, sid, "I need help with SaaS ads")
    _chat(client, sid, "Company is BrightDesk, budget around $5k/month")
    created = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert created["lead_created"] is True
    assert created["lead_id"] is not None
    lead_id = created["lead_id"]

    # Repeating the same details must not create a duplicate lead.
    again = _chat(client, sid, "My name is Sam, email sam@brightdesk.example")
    assert again["lead_id"] == lead_id
    assert again["action"] == "lead_already_exists"

    leads = client.get("/crm/leads").json()
    matching = [x for x in leads if x["id"] == lead_id]
    assert len(matching) == 1
    assert matching[0]["company"] == "BrightDesk"


def test_terse_flow_creates_lead_after_final_field(client: TestClient) -> None:
    # Mirrors the documented example flow with terse, natural replies; the lead
    # must appear only after the final (name + email) message.
    sid = _sid("terse")
    _chat(client, sid, "Hello, I need help with marketing")
    _chat(client, sid, "Paid ads for my SaaS")
    partial = _chat(client, sid, "BrightDesk, around $5k/month")
    assert partial["lead_draft"].get("company") == "BrightDesk"
    assert partial["lead_created"] is False
    created = _chat(client, sid, "Sam, sam@brightdesk.example")
    assert created["lead_created"] is True
    assert created["lead_id"] is not None


def test_service_question_uses_knowledge_source(client: TestClient) -> None:
    data = _chat(client, _sid("svc"), "What services do you provide?")
    assert data["intent"] == "service_question"
    assert data["sources"]


def test_pricing_question_uses_knowledge_source(client: TestClient) -> None:
    data = _chat(client, _sid("price"), "What pricing packages are available?")
    assert data["intent"] == "pricing_question"
    assert data["sources"]


def test_human_request_creates_ticket(client: TestClient) -> None:
    data = _chat(client, _sid("human"), "I need a human manager for a custom enterprise marketing workflow.")
    assert data["intent"] == "human_escalation"
    assert data["ticket_created"] is True
    assert data["ticket_id"] is not None


def test_unknown_asks_clarification_without_ticket(client: TestClient) -> None:
    data = _chat(client, _sid("unk"), "qwerty zxcvbn asdfgh")
    assert data["action"] == "asked_clarification"
    assert data["ticket_created"] is False
    assert data["ticket_id"] is None
