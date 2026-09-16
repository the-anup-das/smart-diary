"""cognition signals on feedback reports and the mind_logs table

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "cognition_data" not in {c["name"] for c in inspector.get_columns("feedback_reports")}:
        op.add_column("feedback_reports", sa.Column("cognition_data", sa.JSON(), nullable=True))
    if not inspector.has_table("mind_logs"):
        op.create_table(
            "mind_logs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.String(), nullable=False),
            sa.Column("builder", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_mind_logs_user_id", "mind_logs", ["user_id"], unique=False)
        op.create_index("ix_mind_logs_user_date", "mind_logs", ["user_id", "date"], unique=False)


def downgrade():
    op.drop_table("mind_logs")
    op.drop_column("feedback_reports", "cognition_data")
