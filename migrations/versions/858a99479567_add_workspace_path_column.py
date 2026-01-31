"""add_workspace_path_column

Revision ID: 858a99479567
Revises: e17cb2e34d2f
Create Date: 2026-01-30 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '858a99479567'
down_revision: Union[str, Sequence[str], None] = 'e17cb2e34d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add workspace_path column to task table if it doesn't already exist
    conn = op.get_bind()

    # Check if column exists
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('task')]

    if 'workspace_path' not in columns:
        op.add_column('task', sa.Column('workspace_path', sa.VARCHAR(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove workspace_path column from task table
    # SQLite doesn't support DROP COLUMN directly in older versions
    # This is intentionally not implemented
    raise NotImplementedError("Downgrade not supported for SQLite")
