"""Knowledge-base admin and ingestion endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.repositories import AuditLogRepository
from app.rag.retriever import get_retriever
from app.schemas.knowledge import (
    KnowledgeFileContent,
    KnowledgeFileOut,
    KnowledgeFileUpdate,
)
from app.schemas.metrics import KnowledgeIngestResult

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _kb_root() -> Path:
    root = Path(settings.knowledge_base_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_file(file_path: str) -> Path:
    if not file_path.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md knowledge files are supported")
    root = _kb_root()
    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid knowledge file path") from None
    return target


def _file_out(path: Path, root: Path) -> KnowledgeFileOut:
    text = path.read_text(encoding="utf-8")
    stat = path.stat()
    preview = " ".join(text.strip().split())[:180]
    updated = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return KnowledgeFileOut(
        path=path.relative_to(root).as_posix(),
        size_bytes=stat.st_size,
        updated_at=updated,
        preview=preview,
    )


@router.get("/files", response_model=list[KnowledgeFileOut])
def list_knowledge_files(
    limit: int = Query(default=200, ge=1, le=500),
) -> list[KnowledgeFileOut]:
    """List markdown files in the configured knowledge base."""
    root = _kb_root()
    files = sorted(root.glob("*.md"))[:limit]
    return [_file_out(path, root) for path in files if path.is_file()]


@router.get("/files/{file_path:path}", response_model=KnowledgeFileContent)
def get_knowledge_file(file_path: str) -> KnowledgeFileContent:
    """Read one markdown knowledge-base file."""
    path = _safe_file(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    return KnowledgeFileContent(path=file_path, content=path.read_text(encoding="utf-8"))


@router.put("/files/{file_path:path}", response_model=KnowledgeFileContent)
def upsert_knowledge_file(
    file_path: str,
    payload: KnowledgeFileUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeFileContent:
    """Create or update one markdown knowledge-base file."""
    path = _safe_file(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.content.strip() + "\n", encoding="utf-8")
    AuditLogRepository(db).create(
        actor="admin",
        action="knowledge_file.upserted",
        entity_type="knowledge_file",
        entity_id=file_path,
        summary=f"Saved knowledge file {file_path}",
    )
    return KnowledgeFileContent(path=file_path, content=path.read_text(encoding="utf-8"))


@router.delete(
    "/files/{file_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_knowledge_file(
    file_path: str,
    db: Session = Depends(get_db),
) -> Response:
    """Delete one markdown knowledge-base file."""
    path = _safe_file(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    path.unlink()
    AuditLogRepository(db).create(
        actor="admin",
        action="knowledge_file.deleted",
        entity_type="knowledge_file",
        entity_id=file_path,
        summary=f"Deleted knowledge file {file_path}",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ingest", response_model=KnowledgeIngestResult)
def ingest_knowledge(db: Session = Depends(get_db)) -> KnowledgeIngestResult:
    """(Re)index the markdown knowledge base into the vector store."""
    stats = get_retriever().index_knowledge_base()
    AuditLogRepository(db).create(
        actor="admin",
        action="knowledge_base.reindexed",
        entity_type="knowledge_base",
        summary=f"Re-indexed {stats['documents']} documents into {stats['chunks']} chunks",
        metadata=stats,
    )
    return KnowledgeIngestResult(
        documents=stats["documents"],
        chunks=stats["chunks"],
        collection=stats["collection"],
        embedding_mode=stats["embedding_mode"],
    )
