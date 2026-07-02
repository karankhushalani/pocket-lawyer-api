"""Add conversation_id to chat_messages

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("conversation_id", sa.String(64), nullable=False, server_default="default"),
    )
    op.alter_column("chat_messages", "conversation_id", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_messages", "conversation_id")
