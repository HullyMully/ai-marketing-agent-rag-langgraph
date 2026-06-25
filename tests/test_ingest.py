"""Knowledge ingestion smoke tests."""
from fastapi.testclient import TestClient

from app.config import settings
from app.rag.retriever import get_retriever


def test_ingest_endpoint(client: TestClient) -> None:
    resp = client.post("/knowledge/ingest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents"] >= 5
    assert body["chunks"] > 0


def test_retriever_search_returns_hits() -> None:
    retriever = get_retriever()
    retriever.index_knowledge_base()
    hits = retriever.search("pricing packages", top_k=3)
    assert len(hits) > 0
    assert all(h.text for h in hits)


def test_metrics_endpoint(client: TestClient) -> None:
    resp = client.get("/metrics/demo")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "conversations",
        "leads",
        "tickets",
        "escalation_rate",
        "resolved_by_ai_rate",
    }


def test_knowledge_file_admin_crud_and_ingest(client: TestClient, monkeypatch, tmp_path) -> None:
    original_dir = settings.knowledge_base_dir
    monkeypatch.setattr(settings, "knowledge_base_dir", str(tmp_path))
    try:
        created = client.put(
            "/knowledge/files/services.md",
            json={"content": "# Services\n\nWe run paid ads and lifecycle campaigns."},
        )
        assert created.status_code == 200
        assert created.json()["path"] == "services.md"

        listed = client.get("/knowledge/files")
        assert listed.status_code == 200
        assert any(row["path"] == "services.md" for row in listed.json())

        fetched = client.get("/knowledge/files/services.md")
        assert fetched.status_code == 200
        assert "paid ads" in fetched.json()["content"]

        ingest = client.post("/knowledge/ingest")
        assert ingest.status_code == 200
        assert ingest.json()["documents"] == 1
        assert ingest.json()["chunks"] >= 1

        deleted = client.delete("/knowledge/files/services.md")
        assert deleted.status_code == 204

        audit = client.get("/audit/events")
        assert audit.status_code == 200
        actions = {row["action"] for row in audit.json()}
        assert {
            "knowledge_file.upserted",
            "knowledge_base.reindexed",
            "knowledge_file.deleted",
        }.issubset(actions)
    finally:
        monkeypatch.setattr(settings, "knowledge_base_dir", original_dir)
        get_retriever().index_knowledge_base()
