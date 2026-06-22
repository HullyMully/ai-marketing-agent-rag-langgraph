"""Knowledge-base ingestion endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from app.rag.retriever import get_retriever
from app.schemas.metrics import KnowledgeIngestResult

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/ingest", response_model=KnowledgeIngestResult)
def ingest_knowledge() -> KnowledgeIngestResult:
    """(Re)index the markdown knowledge base into the vector store."""
    stats = get_retriever().index_knowledge_base()
    return KnowledgeIngestResult(
        documents=stats["documents"],
        chunks=stats["chunks"],
        collection=stats["collection"],
        embedding_mode=stats["embedding_mode"],
    )
