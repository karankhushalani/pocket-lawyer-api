from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.services.openai_service import generate_embedding


async def retrieve_relevant_chunks(
    query: str,
    db: AsyncSession,
    top_k: int = 5,
) -> list[DocumentChunk]:
    query_embedding = await generate_embedding(query)
    stmt = (
        select(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
