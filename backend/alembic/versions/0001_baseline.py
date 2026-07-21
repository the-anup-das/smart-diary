"""Baseline — schema as created by models.Base.metadata.create_all().

Existing installs are stamped here; fresh installs get their tables from
create_all() at startup and are then stamped to head. This revision therefore
performs no work itself.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-21

"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
