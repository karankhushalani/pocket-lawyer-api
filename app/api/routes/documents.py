import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session_factory
from app.core.security import get_current_user
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.services.document_parser import extract_text_from_pdf, extract_text_from_image, chunk_text
from app.services.openai_service import generate_embedding
from app.services.rag_service import analyze_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp"}
CONTENT_TYPE_MAP = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}


def _get_ext(filename: str) -> str | None:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext if ext in ALLOWED_EXTENSIONS else None


async def _background_chunk_and_embed(document_id: uuid.UUID, raw_text: str) -> None:
    async with async_session_factory() as db:
        raw_chunks = chunk_text(raw_text)
        for i, chunk_text_content in enumerate(raw_chunks):
            embedding = await generate_embedding(chunk_text_content)
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                chunk_text=chunk_text_content,
                embedding=embedding,
            )
            db.add(chunk)

        await db.commit()


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    document_type: str | None = Form(None),
    jurisdiction: str = Form("india"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = _get_ext(file.filename)
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    # ── Extract text ─────────────────────────────────────────────────
    if ext == "pdf":
        raw_text = await extract_text_from_pdf(file_bytes)
    else:
        raw_text = await extract_text_from_image(file_bytes)

    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from the file",
        )

    # ── Upload to Firebase Storage ────────────────────────────────────
    from app.core.security import get_storage_bucket
    bucket = get_storage_bucket()
    if bucket is None:
        file_url = f"dev://placeholder/{file.filename}"
    else:
        file_uuid = str(uuid.uuid4())
        blob_path = f"users/{current_user.id}/documents/{file_uuid}.{ext}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_bytes, content_type=CONTENT_TYPE_MAP.get(ext, "application/octet-stream"))
        blob.make_public()
        file_url = blob.public_url

    # ── Analyze document ──────────────────────────────────────────────
    analysis = await analyze_document(raw_text, document_type=document_type)

    doc = Document(
        user_id=current_user.id,
        title=title or file.filename or "Untitled",
        file_url=file_url,
        file_type=ext,
        raw_text=raw_text,
        summary=analysis.get("summary", ""),
        document_type=analysis.get("document_type", document_type),
        jurisdiction=jurisdiction,
        key_clauses=analysis.get("key_clauses", []),
        risk_flags=analysis.get("risk_flags", []),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # ── Background: chunk + embed ─────────────────────────────────────
    background_tasks.add_task(_background_chunk_and_embed, doc.id, raw_text)

    return {
        "document_id": str(doc.id),
        "title": doc.title,
        "summary": doc.summary,
        "document_type": doc.document_type,
        "risk_flags": doc.risk_flags or [],
    }


@router.get("/")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "document_type": doc.document_type,
            "summary": doc.summary,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "id": str(doc.id),
        "title": doc.title,
        "file_url": doc.file_url,
        "file_type": doc.file_type,
        "document_type": doc.document_type,
        "jurisdiction": doc.jurisdiction,
        "summary": doc.summary,
        "key_clauses": doc.key_clauses or [],
        "risk_flags": doc.risk_flags or [],
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"detail": "Document deleted"}
