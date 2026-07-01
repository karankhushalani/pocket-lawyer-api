from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.models.chat import ChatMessage
from app.models.user import User
from app.models.document import Document
from app.services.openai_service import chat_completion
from app.services.rag_service import retrieve_relevant_chunks

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages")
async def send_message(
    body: dict,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_result = await db.execute(
        select(User).where(User.firebase_uid == token_data["uid"])
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_message = body.get("message", "")
    document_id = body.get("document_id", None)

    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")

    if document_id:
        doc_result = await db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user.id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    msg = ChatMessage(
        document_id=document_id,
        user_id=user.id,
        role="user",
        content=user_message,
    )
    db.add(msg)
    await db.commit()

    relevant_chunks = await retrieve_relevant_chunks(user_message, db)

    context = "\n\n".join([chunk.chunk_text for chunk in relevant_chunks])
    system_prompt = (
        "You are a helpful legal assistant. Use the following context to answer the user's question. "
        "If the context does not contain relevant information, say so.\n\n"
        f"Context:\n{context}"
    )

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = history_result.scalars().all()

    openai_messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        openai_messages.append({"role": h.role, "content": h.content})

    reply = await chat_completion(openai_messages)

    assistant_msg = ChatMessage(
        document_id=document_id,
        user_id=user.id,
        role="assistant",
        content=reply,
    )
    db.add(assistant_msg)
    await db.commit()

    return {"reply": reply}


@router.get("/messages")
async def list_messages(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    user_result = await db.execute(
        select(User).where(User.firebase_uid == token_data["uid"])
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = messages_result.scalars().all()
    return [
        {
            "id": str(m.id),
            "document_id": str(m.document_id) if m.document_id else None,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
