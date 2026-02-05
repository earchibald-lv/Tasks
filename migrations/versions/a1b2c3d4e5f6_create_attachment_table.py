"""Create attachment table for dual-index support.

Revision ID: a1b2c3d4e5f6
Revises: 9a1b2c3d4e5f
Create Date: 2026-02-04 19:52:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the attachment table."""
    op.create_table(
        'attachment',
        sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('storage_filename', sa.String(), nullable=False),
        sa.Column('file_data', sa.LargeBinary(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'original_filename', name='uq_attachment_task_original_filename'),
    )
    op.create_index(op.f('ix_attachment_created_at'), 'attachment', ['created_at'], unique=False)
    op.create_index(op.f('ix_attachment_task_id'), 'attachment', ['task_id'], unique=False)


def downgrade() -> None:
    """Drop the attachment table."""
    op.drop_index(op.f('ix_attachment_task_id'), table_name='attachment')
    op.drop_index(op.f('ix_attachment_created_at'), table_name='attachment')
    op.drop_table('attachment')
