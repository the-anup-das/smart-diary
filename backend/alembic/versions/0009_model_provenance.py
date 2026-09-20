"""which model and prompt produced each feedback report

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

COLUMNS = ("model_provider", "model_name", "prompt_version")


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("feedback_reports")}
    for name in COLUMNS:
        if name not in existing:
            op.add_column("feedback_reports", sa.Column(name, sa.String(), nullable=True))


def downgrade():
    for name in COLUMNS:
        op.drop_column("feedback_reports", name)
