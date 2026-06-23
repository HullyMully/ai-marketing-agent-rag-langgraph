"""FastAPI application entry point for the AI Customer Assistant.

Run locally:
    uvicorn app.main:app --reload

Swagger docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, crm, knowledge, metrics, tickets
from app.company import get_company
from app.config import settings
from app.db.database import init_db

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database and warm the RAG index on startup."""
    init_db()
    try:
        from app.rag.retriever import get_retriever

        get_retriever().ensure_ready()
    except Exception as exc:  # pragma: no cover - non-fatal warm-up
        logger.warning("Knowledge base warm-up skipped: %s", exc)
    logger.info("Assistant ready (mock_llm=%s).", settings.mock_llm)
    yield


app = FastAPI(
    title="AI Customer Assistant",
    description=(
        "A configurable AI customer assistant platform (LangGraph + RAG + Qdrant) "
        "with a web chat, knowledge-base answers, lead qualification, CRM-style "
        "lead creation, support-ticket escalation and session memory. Configure "
        "your business profile and knowledge base to use it for your own company. "
        "Sample data shipped with the project is fictional."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(crm.router)
app.include_router(tickets.router)
app.include_router(knowledge.router)
app.include_router(metrics.router)

# Serve the web UI (plain HTML/CSS/JS).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def landing_page() -> FileResponse:
    """Product landing page."""
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/demo", response_class=FileResponse, include_in_schema=False)
def web_chat() -> FileResponse:
    """Web chat assistant, wired to POST /chat."""
    return FileResponse(TEMPLATES_DIR / "demo.html")


@app.get("/api-overview", response_class=FileResponse, include_in_schema=False)
def api_overview_page() -> FileResponse:
    """Product-style overview of the API endpoints (styled, not Swagger)."""
    return FileResponse(TEMPLATES_DIR / "api-overview.html")


@app.get("/metrics", response_class=FileResponse, include_in_schema=False)
def metrics_page() -> FileResponse:
    """Visual metrics dashboard backed by GET /metrics/demo."""
    return FileResponse(TEMPLATES_DIR / "metrics.html")


@app.get("/config", tags=["system"])
def public_config() -> dict:
    """Public, non-secret business profile used by the web UI."""
    return get_company().public_dict()


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "mock_llm": settings.mock_llm}
