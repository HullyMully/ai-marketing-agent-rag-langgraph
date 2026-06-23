"""Tests for the local web demo pages and static assets."""
from fastapi.testclient import TestClient


def test_landing_page_ok(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "NovaGrowth" in resp.text


def test_demo_page_ok(client: TestClient) -> None:
    resp = client.get("/demo")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/static/styles.css" in resp.text
    assert "/static/demo.js" in resp.text


def test_api_overview_page_ok(client: TestClient) -> None:
    resp = client.get("/api-overview")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/chat" in resp.text


def test_metrics_page_ok(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Demo metrics" in resp.text


def test_static_css_loads(client: TestClient) -> None:
    resp = client.get("/static/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_js_loads(client: TestClient) -> None:
    resp = client.get("/static/demo.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
