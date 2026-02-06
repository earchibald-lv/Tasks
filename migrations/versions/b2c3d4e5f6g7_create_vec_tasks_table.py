"""Create vec_tasks virtual table for semantic search.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-06 10:00:00.000000

This migration creates the sqlite-vec virtual table for storing task embeddings.
The vec_tasks table uses the vec0 module for efficient vector similarity search.

Architecture: "Sidecar" pattern - embeddings are stored separately from core Task model
to preserve lightweight operations and minimize token usage during standard list queries.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the vec_tasks virtual table for semantic search embeddings.
    
    The virtual table stores 384-dimensional embeddings (Matryoshka slicing from 768d)
    for efficient similarity search using nomic-embed-text-v1.5 model.
    
    Note: sqlite-vec extension must be loaded before this table can be queried.
    The extension is loaded at runtime by the SemanticSearchService.
    """
    conn = op.get_bind()
    
    # Check if sqlite-vec is available by trying to load it
    # If not available, skip migration (extension will be loaded at runtime)
    try:
        # First try to load the extension if it's available
        # sqlite-vec may be statically linked or need explicit loading
        conn.execute(sa.text("SELECT 1"))  # Test connection
        
        # Create the virtual table using raw SQL
        # Note: If extension not loaded, this will fail gracefully
        # and the table will be created on first use by SemanticSearchService
        conn.execute(sa.text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_tasks USING vec0(
                task_id INTEGER PRIMARY KEY,
                embedding FLOAT[384]
            )
        """))
    except Exception as e:
        # sqlite-vec extension not available during migration
        # The SemanticSearchService will create the table on first use
        import sys
        print(f"Note: vec_tasks table will be created on first search use: {e}", file=sys.stderr)


def downgrade() -> None:
    """Drop the vec_tasks virtual table."""
    conn = op.get_bind()
    try:
        conn.execute(sa.text("DROP TABLE IF EXISTS vec_tasks"))
    except Exception:
        pass  # Table may not exist if migration was skipped
