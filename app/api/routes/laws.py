from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.database import get_db
from app.core.security import verify_token
from app.models.law import LawChunk
from app.services.openai_service import generate_embedding, chat_completion

router = APIRouter(prefix="/laws", tags=["laws"])


@router.get("/search")
async def search_laws(
    query: str,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query_embedding = await generate_embedding(query)
    stmt = (
        select(LawChunk)
        .order_by(LawChunk.embedding.cosine_distance(query_embedding))
        .limit(5)
    )
    result = await db.execute(stmt)
    relevant_chunks = list(result.scalars().all())

    context = "\n\n".join(
        f"[{c.act_short} - {c.section}] {c.chunk_text}" for c in relevant_chunks
    )

    system_prompt = (
        "You are a legal research assistant. Based on the provided Indian law context, "
        "answer the user's question. Cite the specific act and section when possible.\n\n"
        f"Context:\n{context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    answer = await chat_completion(messages)
    return {"answer": answer, "sources": len(relevant_chunks)}


@router.get("/external/{jurisdiction}")
async def external_law_lookup(
    jurisdiction: str,
    query: str,
    token_data: dict = Depends(verify_token),
) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.example.com/laws/{jurisdiction}",
            params={"q": query},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
