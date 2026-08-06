"""add performance indexes

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-06 17:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    # JournalEntry indexes
    op.create_index(op.f('ix_journal_entries_user_id'), 'journal_entries', ['user_id'], unique=False)
    op.create_index(op.f('ix_journal_entries_is_deleted'), 'journal_entries', ['is_deleted'], unique=False)
    op.create_index('ix_journal_entries_user_is_deleted_date', 'journal_entries', ['user_id', 'is_deleted', 'date'], unique=False)
    
    # OpenLoop indexes
    op.create_index(op.f('ix_open_loops_user_id'), 'open_loops', ['user_id'], unique=False)
    op.create_index(op.f('ix_open_loops_status'), 'open_loops', ['status'], unique=False)
    
    # Decision indexes
    op.create_index(op.f('ix_decisions_user_id'), 'decisions', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_decisions_user_id'), table_name='decisions')
    op.drop_index(op.f('ix_open_loops_status'), table_name='open_loops')
    op.drop_index(op.f('ix_open_loops_user_id'), table_name='open_loops')
    op.drop_index('ix_journal_entries_user_is_deleted_date', table_name='journal_entries')
    op.drop_index(op.f('ix_journal_entries_is_deleted'), table_name='journal_entries')
    op.drop_index(op.f('ix_journal_entries_user_id'), table_name='journal_entries')
