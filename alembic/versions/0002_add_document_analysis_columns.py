"""Add document analysis columns and law_chunks constraints

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── documents: new columns ─────────────────────────────────────────
    op.add_column("documents", sa.Column("key_clauses", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("risk_flags", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column(
        "deleted_at", sa.DateTime(timezone=True), nullable=True
    ))

    # ── law_chunks: add chunk_index + unique constraint ─────────────────
    op.add_column("law_chunks", sa.Column(
        "chunk_index", sa.Integer(), nullable=False, server_default=sa.text("0")
    ))
    op.create_unique_constraint(
        "uq_law_chunks_act_section_idx",
        "law_chunks",
        ["act_name", "section", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_law_chunks_act_section_idx", "law_chunks", type_="unique")
    op.drop_column("law_chunks", "chunk_index")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "risk_flags")
    op.drop_column("documents", "key_clauses")
