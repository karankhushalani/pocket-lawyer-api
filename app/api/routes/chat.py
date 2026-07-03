from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.chat import ChatMessage
from app.models.document import Document
from app.models.user import User
from app.services.openai_service import chat_completion
from app.services.rag_service import build_legal_context

router = APIRouter(prefix="/chat", tags=["chat"])


LEX_SYSTEM_PROMPT = (
    "You are Lex, an AI legal assistant specializing in Indian law. You help users "
    "understand legal documents and Indian statutes.\n\n"
    "Rules:\n"
    "- Always cite specific sections when referencing statutes "
    "(e.g., 'Under Section 302 of IPC...')\n"
    "- Always add a disclaimer: 'This is general legal information, not legal advice. "
    "Consult a qualified lawyer for your specific situation.'\n"
    "- If you don't know something, say so \u2014 never fabricate legal references\n"
    "- Keep responses clear and accessible, avoiding unnecessary jargon\n"
    "- Focus on Indian jurisdiction unless asked otherwise"
)


@router.post("")
async def send_message(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_message = body.get("message", "")
    document_id = body.get("document_id")
    conversation_id = body.get("conversation_id") or "default"

    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required",
        )

    if document_id:
        doc_result = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
        if doc_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

    ctx = await build_legal_context(user_message, db, document_id=document_id)

    context_parts = [ctx["law_context"], ctx["document_context"]]
    context = "\n\n".join(p for p in context_parts if p)

    history_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user.id,
            ChatMessage.conversation_id == conversation_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(6)
    )
    history = list(reversed(history_result.scalars().all()))

    openai_messages = [{"role": "system", "content": LEX_SYSTEM_PROMPT}]
    for h in history:
        openai_messages.append({"role": h.role, "content": h.content})

    user_msg_content = user_message
    if context:
        user_msg_content = f"Context:\n{context}\n\nUser question:\n{user_message}"
    openai_messages.append({"role": "user", "content": user_msg_content})

    reply = await chat_completion(openai_messages, model="gpt-4o", max_tokens=4096)

    user_msg = ChatMessage(
        conversation_id=conversation_id,
        document_id=document_id,
        user_id=user.id,
        role="user",
        content=user_message,
    )
    assistant_msg = ChatMessage(
        conversation_id=conversation_id,
        document_id=document_id,
        user_id=user.id,
        role="assistant",
        content=reply,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()

    sources = []
    for s in ctx["sources"]:
        if s["type"] == "law":
            sources.append({"act_name": s["act_name"], "section": s["section"]})

    return {
        "response": reply,
        "sources": sources,
        "message_id": str(assistant_msg.id),
    }


@router.get("/history/{document_id}")
async def get_document_history(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    doc_result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == user.id
        )
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    messages_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user.id,
            ChatMessage.document_id == document_id,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    messages = messages_result.scalars().all()
    return [
        {
            "id": str(m.id),
            "conversation_id": m.conversation_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
