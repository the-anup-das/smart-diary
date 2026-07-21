"""Repair columns added by the legacy migrate_*.py scripts.

Those scripts ran all ALTERs in one transaction, so the first "column already
exists" error silently aborted the rest and left installs half-migrated. This
revision re-applies every historical column idempotently (IF NOT EXISTS), so a
single `alembic upgrade head` heals any install regardless of which legacy
scripts succeeded.

Revision ID: 0002_repair_columns
Revises: 0001_baseline
Create Date: 2026-07-21

"""
from alembic import op

revision = "0002_repair_columns"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("journal_entries", "is_deleted", "BOOLEAN DEFAULT FALSE"),
    ("journal_entries", "deleted_at", "TIMESTAMP WITHOUT TIME ZONE"),
    ("users", "preferences", "JSONB"),
    ("feedback_reports", "self_focus_score", "INTEGER"),
    ("feedback_reports", "self_focus_feedback", "TEXT"),
    ("feedback_reports", "repetitive_wording", "JSONB"),
    ("feedback_reports", "detected_decision", "TEXT"),
    ("feedback_reports", "energy_data", "JSONB"),
    ("feedback_reports", "prompt_tokens", "INTEGER DEFAULT 0"),
    ("feedback_reports", "completion_tokens", "INTEGER DEFAULT 0"),
    ("feedback_reports", "total_tokens", "INTEGER DEFAULT 0"),
    ("feedback_reports", "word_count", "INTEGER"),
    ("feedback_reports", "unique_word_count", "INTEGER"),
    ("feedback_reports", "new_words", "JSONB"),
    ("feedback_reports", "content_hash", "VARCHAR"),
    ("decisions", "analysis_result", "JSON"),
    ("decisions", "framework", "VARCHAR"),
    ("decisions", "primary_option_id", "VARCHAR"),
    ("decisions", "expected_outcome", "TEXT"),
    ("decisions", "actual_outcome", "TEXT"),
    ("decisions", "review_date", "TIMESTAMP WITHOUT TIME ZONE"),
]


def upgrade() -> None:
    for table, column, ddl_type in _COLUMNS:
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl_type}')


def downgrade() -> None:
    # Repair-only revision: columns are part of the live schema, never dropped.
    pass
