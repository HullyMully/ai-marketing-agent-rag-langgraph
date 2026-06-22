"""Knowledge ingestion smoke tests."""
from fastapi.testclient import TestClient

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
