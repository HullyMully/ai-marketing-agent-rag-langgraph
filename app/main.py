"""FastAPI application entry point for the NovaGrowth AI marketing agent.

Run locally:
    uvicorn app.main:app --reload

Swagger docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import chat, crm, knowledge, metrics, tickets
from app.config import settings
from app.db.database import init_db

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("novagrowth")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database and warm the RAG index on startup."""
    init_db()
    try:
        from app.rag.retriever import get_retriever

        get_retriever().ensure_ready()
    except Exception as exc:  # pragma: no cover - non-fatal warm-up
        logger.warning("Knowledge base warm-up skipped: %s", exc)
    logger.info("NovaGrowth agent ready (mock_llm=%s).", settings.mock_llm)
    yield


app = FastAPI(
    title="NovaGrowth AI Marketing Agent",
    description=(
        "Portfolio case study. Fictional company. Not affiliated with any real "
        "business. A conversational AI agent (LangGraph + RAG + Qdrant) for a "
        "fictional digital marketing agency, with FastAPI, a mock CRM, support "
        "tickets and human escalation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(crm.router)
app.include_router(tickets.router)
app.include_router(knowledge.router)
app.include_router(metrics.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "mock_llm": settings.mock_llm}
