from collections.abc import AsyncGenerator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding "
                "ON document_chunks USING ivfflat (embedding vector_cosine_ops) "
                "WITH (lists = 100)"
            )
        )
        await conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_law_chunks_embedding "
                "ON law_chunks USING ivfflat (embedding vector_cosine_ops) "
                "WITH (lists = 100)"
            )
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
