"""stimulation signals on feedback reports and the Focus Reset tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-16 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "stimulation_data" not in {c["name"] for c in inspector.get_columns("feedback_reports")}:
        op.add_column("feedback_reports", sa.Column("stimulation_data", sa.JSON(), nullable=True))

    if not inspector.has_table("focus_plans"):
        op.create_table(
            "focus_plans",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("behaviour", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("objectives", sa.Text(), nullable=True),
            sa.Column("problems", sa.Text(), nullable=True),
            sa.Column("abstinence_days", sa.Integer(), nullable=True),
            sa.Column("start_date", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("rules", sa.JSON(), nullable=True),
            sa.Column("replacements", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_focus_plans_user_id", "focus_plans", ["user_id"], unique=False)

    if not inspector.has_table("focus_urges"):
        op.create_table(
            "focus_urges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_id", sa.String(), sa.ForeignKey("focus_plans.id", ondelete="SET NULL"), nullable=True),
            sa.Column("logged_at", sa.DateTime(), nullable=True),
            sa.Column("intensity", sa.Integer(), nullable=True),
            sa.Column("acted", sa.Boolean(), nullable=True),
            sa.Column("trigger", sa.String(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
        )
        op.create_index("ix_focus_urges_user_id", "focus_urges", ["user_id"], unique=False)
        op.create_index("ix_focus_urges_logged_at", "focus_urges", ["logged_at"], unique=False)

    if not inspector.has_table("focus_checkins"):
        op.create_table(
            "focus_checkins",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_id", sa.String(), sa.ForeignKey("focus_plans.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.String(), nullable=False),
            sa.Column("urges", sa.Integer(), nullable=True),
            sa.Column("gave_in", sa.Boolean(), nullable=True),
            sa.Column("sleep_ok", sa.Boolean(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_focus_checkins_user_id", "focus_checkins", ["user_id"], unique=False)
        op.create_index("ix_focus_checkins_plan_id", "focus_checkins", ["plan_id"], unique=False)


def downgrade():
    op.drop_table("focus_checkins")
    op.drop_table("focus_urges")
    op.drop_table("focus_plans")
    op.drop_column("feedback_reports", "stimulation_data")
