"""Wellbeing fields: emotion labels + distress flag on feedback reports.

Revision ID: 0004_wellbeing_fields
Revises: 0003_chat_and_feedback
Create Date: 2026-07-21

"""
from alembic import op

revision = "0004_wellbeing_fields"
down_revision = "0003_chat_and_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE feedback_reports ADD COLUMN IF NOT EXISTS emotion_labels JSONB")
    op.execute("ALTER TABLE feedback_reports ADD COLUMN IF NOT EXISTS distress_flag BOOLEAN DEFAULT FALSE")


def downgrade() -> None:
    op.execute("ALTER TABLE feedback_reports DROP COLUMN IF EXISTS emotion_labels")
    op.execute("ALTER TABLE feedback_reports DROP COLUMN IF EXISTS distress_flag")
