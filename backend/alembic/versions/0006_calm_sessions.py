"""add calm_sessions for the 3-Minute Reset

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: a database bootstrapped by create_all() may already carry the table.
    if sa.inspect(op.get_bind()).has_table("calm_sessions"):
        return
    op.create_table(
        "calm_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_id", sa.String(), sa.ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("rumination_level", sa.String(), nullable=True),
        sa.Column("rumination_type", sa.String(), nullable=True),
        sa.Column("loop_thought", sa.Text(), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("personalized", sa.Boolean(), nullable=True),
        sa.Column("source_hash", sa.String(), nullable=True),
        sa.Column("mind_before", sa.Integer(), nullable=True),
        sa.Column("mind_after", sa.Integer(), nullable=True),
        sa.Column("steps_completed", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_calm_sessions_user_id", "calm_sessions", ["user_id"], unique=False)
    op.create_index("ix_calm_sessions_started_at", "calm_sessions", ["started_at"], unique=False)


def downgrade():
    op.drop_index("ix_calm_sessions_started_at", table_name="calm_sessions")
    op.drop_index("ix_calm_sessions_user_id", table_name="calm_sessions")
    op.drop_table("calm_sessions")
