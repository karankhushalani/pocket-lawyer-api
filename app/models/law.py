import uuid

from sqlalchemy import String, Text, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class LawChunk(Base):
    __tablename__ = "law_chunks"

    __table_args__ = (
        UniqueConstraint(
            "act_name", "section", "chunk_index",
            name="uq_law_chunks_act_section_idx",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    act_name: Mapped[str] = mapped_column(String(256), nullable=False)
    act_short: Mapped[str] = mapped_column(String(32), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)
