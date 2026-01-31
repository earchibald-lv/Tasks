"""add_autoincrement_to_task_id

Revision ID: 9a1b2c3d4e5f
Revises: 858a99479567
Create Date: 2026-01-30 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '858a99479567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add AUTOINCREMENT to task.id.

    SQLite doesn't support modifying PRIMARY KEY constraints, so we need to:
    1. Create a new table with AUTOINCREMENT
    2. Copy all data from the old table
    3. Drop the old table
    4. Rename the new table
    5. Recreate indexes
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if task table exists
    tables = inspector.get_table_names()
    if 'task' not in tables:
        return

    # Get all columns from existing task table
    columns = inspector.get_columns('task')
    column_names = [col['name'] for col in columns]

    # Get existing indexes before dropping the table
    existing_indexes = inspector.get_indexes('task')

    # Check if we need to add missing columns from model
    missing_columns = []
    expected_columns = {
        'jira_issues': ('VARCHAR', True),
        'tags': ('VARCHAR', True),
        'attachments': ('VARCHAR', True),
        'workspace_path': ('VARCHAR', True),
    }

    for col_name, (col_type, nullable) in expected_columns.items():
        if col_name not in column_names:
            missing_columns.append((col_name, col_type, nullable))

    # Build column definitions for CREATE TABLE
    create_columns = []
    for col in columns:
        col_name = col['name']
        col_type = str(col['type'])
        nullable = '' if col['nullable'] else ' NOT NULL'

        if col_name == 'id':
            # Add AUTOINCREMENT to id column
            create_columns.append('id INTEGER PRIMARY KEY AUTOINCREMENT')
        else:
            create_columns.append(f'{col_name} {col_type}{nullable}')

    # Add missing columns to new table
    for col_name, col_type, nullable in missing_columns:
        null_str = ' NULL' if nullable else ' NOT NULL'
        create_columns.append(f'{col_name} {col_type}{null_str}')

    create_table_sql = f"CREATE TABLE task_new ({', '.join(create_columns)})"

    # Execute the migration
    conn.execute(sa.text(create_table_sql))

    # Copy data from old table to new table
    copy_columns = ', '.join(column_names)
    conn.execute(sa.text(f'INSERT INTO task_new ({copy_columns}) SELECT {copy_columns} FROM task'))

    # Drop old table
    conn.execute(sa.text('DROP TABLE task'))

    # Rename new table
    conn.execute(sa.text('ALTER TABLE task_new RENAME TO task'))

    # Recreate indexes from the old table
    for idx in existing_indexes:
        idx_name = idx['name']
        idx_columns = ', '.join(idx['column_names'])
        conn.execute(sa.text(f'CREATE INDEX {idx_name} ON task ({idx_columns})'))

    # Create indexes for new columns if they were added
    if 'tags' in [col_name for col_name, _, _ in missing_columns]:
        conn.execute(sa.text('CREATE INDEX ix_task_tags ON task (tags)'))


def downgrade() -> None:
    """Downgrade schema."""
    # Cannot downgrade AUTOINCREMENT in SQLite without recreating the table
    # This would require keeping track of the original max ID, which is complex
    raise NotImplementedError("Downgrade not supported for this migration")
