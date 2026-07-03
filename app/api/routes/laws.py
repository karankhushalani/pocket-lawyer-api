from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.models.law import LawChunk
from app.services.rag_service import search_law_chunks

router = APIRouter(prefix="/laws", tags=["laws"])


@router.get("")
async def list_acts(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(
            LawChunk.act_name,
            LawChunk.act_short,
            func.count().label("chunk_count"),
        )
        .group_by(LawChunk.act_name, LawChunk.act_short)
        .order_by(LawChunk.act_name)
    )
    result = await db.execute(stmt)
    return [
        {"act_name": row.act_name, "act_short": row.act_short, "chunk_count": row.chunk_count}
        for row in result.all()
    ]


@router.get("/search")
async def search_laws(
    q: str = Query(..., description="Search query"),
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' is required",
        )

    chunks = await search_law_chunks(q, db, top_k=10)
    return [
        {
            "act_name": c["act_name"],
            "section": c["section"],
            "chunk_text": c["chunk_text"],
            "similarity": c["similarity_score"],
        }
        for c in chunks
    ]


@router.get("/{act_short}")
async def get_act_sections(
    act_short: str,
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    first_chunk_per_section = (
        select(
            LawChunk.section,
            func.min(LawChunk.chunk_index).label("min_index"),
        )
        .where(LawChunk.act_short == act_short.upper())
        .group_by(LawChunk.section)
        .subquery()
    )

    stmt = (
        select(LawChunk)
        .join(
            first_chunk_per_section,
            (LawChunk.section == first_chunk_per_section.c.section)
            & (LawChunk.chunk_index == first_chunk_per_section.c.min_index),
        )
        .where(LawChunk.act_short == act_short.upper())
        .order_by(LawChunk.section)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Act '{act_short}' not found",
        )

    return [
        {
            "act_name": c.act_name,
            "act_short": c.act_short,
            "section": c.section,
            "chunk_text": c.chunk_text[:500] + ("..." if len(c.chunk_text) > 500 else ""),
        }
        for c in chunks
    ]
