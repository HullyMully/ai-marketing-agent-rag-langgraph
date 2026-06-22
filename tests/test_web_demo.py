"""Smoke tests for the local web demo (landing page, demo chat, static files)."""
from fastapi.testclient import TestClient


def test_landing_page_ok(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AI Marketing Agent" in resp.text


def test_demo_page_ok(client: TestClient) -> None:
    resp = client.get("/demo")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Demo mode" in resp.text


def test_static_css_served(client: TestClient) -> None:
    resp = client.get("/static/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_existing_routes_still_work(client: TestClient) -> None:
    # The web demo must not break existing API routes or the OpenAPI schema.
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200
