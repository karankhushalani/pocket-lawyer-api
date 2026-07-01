from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.services.document_parser import extract_text_from_pdf, chunk_text
from app.services.openai_service import generate_embedding

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    file_type: str = Form("pdf"),
    document_type: str | None = Form(None),
    jurisdiction: str = Form("india"),
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    file_bytes = await file.read()
    raw_text = extract_text_from_pdf(file_bytes)

    result = await db.execute(
        select(User).where(User.firebase_uid == token_data["uid"])
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    document = Document(
        user_id=user.id,
        title=title,
        file_url="",  # caller should update with Firebase Storage URL after upload
        file_type=file_type,
        raw_text=raw_text,
        document_type=document_type,
        jurisdiction=jurisdiction,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    raw_chunks = chunk_text(raw_text)
    for i, chunk_text_content in enumerate(raw_chunks):
        embedding = await generate_embedding(chunk_text_content)
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=i,
            chunk_text=chunk_text_content,
            embedding=embedding,
        )
        db.add(chunk)
    await db.commit()

    return {
        "document_id": str(document.id),
        "title": document.title,
        "chunks": len(raw_chunks),
    }


@router.get("/")
async def list_documents(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(User).where(User.firebase_uid == token_data["uid"])
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    docs_result = await db.execute(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    documents = docs_result.scalars().all()
    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "file_type": doc.file_type,
            "document_type": doc.document_type,
            "jurisdiction": doc.jurisdiction,
            "summary": doc.summary,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.id == document_id)
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
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(document)
    await db.commit()
    return {"detail": "Document deleted"}
