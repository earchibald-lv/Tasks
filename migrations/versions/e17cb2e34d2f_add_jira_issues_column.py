"""add_jira_issues_column

Revision ID: e17cb2e34d2f
Revises: 
Create Date: 2026-01-29 15:44:01.224660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e17cb2e34d2f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add jira_issues column to task table if it doesn't already exist
    # We use a try/except because SQLite doesn't have IF NOT EXISTS for ALTER TABLE
    conn = op.get_bind()
    
    # Check if column exists
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('task')]
    
    if 'jira_issues' not in columns:
        op.add_column('task', sa.Column('jira_issues', sa.VARCHAR(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove jira_issues column from task table
    # SQLite doesn't support DROP COLUMN directly in older versions
    # This is intentionally not implemented
    raise NotImplementedError("Downgrade not supported for SQLite")
