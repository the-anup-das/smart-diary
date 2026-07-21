"""Add chat_conversations and ai_feedback tables.

Guarded with inspector checks because fresh installs may already have these
tables from create_all() before being stamped.

Revision ID: 0003_chat_and_feedback
Revises: 0002_repair_columns
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_chat_and_feedback"
down_revision = "0002_repair_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "chat_conversations" not in existing:
        op.create_table(
            "chat_conversations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("messages", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if "ai_feedback" not in existing:
        op.create_table(
            "ai_feedback",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("ref_id", sa.String(), nullable=True),
            sa.Column("vote", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("ai_feedback")
    op.drop_table("chat_conversations")
