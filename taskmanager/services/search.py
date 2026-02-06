"""Semantic search service for episodic memory capabilities.

This module provides vector-based semantic search using fastembed and sqlite-vec,
enabling agents to search for similar tasks and learn from past solutions.

Architecture:
- Embeddings stored in separate vec_tasks virtual table ("sidecar" pattern)
- Uses nomic-embed-text-v1.5 with 384 dimensions (Matryoshka slicing)
- Lazy-loads embedding model to prevent CLI startup lag
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Try pysqlite3 first (has extension support), fall back to sqlite3
try:
    import pysqlite3.dbapi2 as sqlite3
except ImportError:
    import sqlite3

if TYPE_CHECKING:
    from fastembed import TextEmbedding

    from taskmanager.models import Task

# Lazy import for fastembed to prevent startup lag
_embedding_model = None
_sqlite_vec_loaded = False


class SemanticSearchService:
    """Service for semantic search and episodic memory operations.

    This service provides:
    - Task embedding generation and storage
    - Semantic similarity search
    - Duplicate detection for "capture" workflows
    - Episodic memory retrieval for learning from past solutions

    Attributes:
        db_path: Path to the SQLite database file
        cache_dir: Directory for fastembed model cache
    """

    # Model configuration
    MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_DIM = 384  # Matryoshka slicing from 768d
    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "fastembed"

    def __init__(self, db_path: str | Path, cache_dir: Path | None = None) -> None:
        """Initialize the semantic search service.

        Args:
            db_path: Path to the SQLite database file
            cache_dir: Optional custom cache directory for fastembed models
        """
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self._model = None
        self._connection: sqlite3.Connection | None = None

    def _get_model(self) -> TextEmbedding:
        """Lazy-load the embedding model.

        Returns:
            TextEmbedding: The fastembed text embedding model

        Raises:
            ImportError: If fastembed is not installed
        """
        global _embedding_model

        if _embedding_model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as e:
                raise ImportError(
                    "fastembed is required for semantic search. Install with: pip install fastembed"
                ) from e

            # Initialize model with cache directory
            _embedding_model = TextEmbedding(
                model_name=self.MODEL_NAME,
                cache_dir=str(self.cache_dir),
            )

        return _embedding_model

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection with sqlite-vec loaded.

        Returns:
            sqlite3.Connection: Connection with vec0 extension loaded

        Raises:
            RuntimeError: If sqlite-vec cannot be loaded
        """
        global _sqlite_vec_loaded

        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))

            # Load sqlite-vec extension
            if not _sqlite_vec_loaded:
                try:
                    import sqlite_vec

                    # Try to enable extension loading if supported
                    if hasattr(self._connection, "enable_load_extension"):
                        self._connection.enable_load_extension(True)
                        sqlite_vec.load(self._connection)
                        self._connection.enable_load_extension(False)
                    else:
                        # Fallback: Try direct loading (works with statically-linked builds)
                        sqlite_vec.load(self._connection)
                    _sqlite_vec_loaded = True
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to load sqlite-vec extension: {e}. "
                        "Install with: pip install sqlite-vec"
                    ) from e

            # Ensure vec_tasks table exists
            self._ensure_vec_table()

        return self._connection

    def _ensure_vec_table(self) -> None:
        """Create the vec_tasks virtual table if it doesn't exist."""
        conn = self._connection
        if conn is None:
            return

        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_tasks USING vec0(
                    task_id INTEGER PRIMARY KEY,
                    embedding FLOAT[384]
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not create vec_tasks table: {e}", file=sys.stderr)

    def _generate_embedding(self, text: str, mode: str = "storage") -> list[float]:
        """Generate embedding for text with appropriate prefix.

        Nomic embed requires specific prefixes for optimal performance:
        - "search_document: " for indexing/storage
        - "search_query: " for retrieval/search queries

        Args:
            text: The text to embed
            mode: Either "storage" or "query"

        Returns:
            List of floats representing the 384-dim embedding
        """
        model = self._get_model()

        # Apply Nomic-specific prefix
        if mode == "storage":
            prefixed_text = f"search_document: {text}"
        else:  # query
            prefixed_text = f"search_query: {text}"

        # Generate embedding (returns generator, take first result)
        embeddings = list(model.embed([prefixed_text]))
        full_embedding: list[float] = embeddings[0].tolist()

        # Matryoshka slicing: take first 384 dimensions
        return full_embedding[: self.EMBEDDING_DIM]

    def _build_task_content(self, task: Task) -> str:
        """Build searchable content string from a task.

        Args:
            task: The task to build content for

        Returns:
            Concatenated content string for embedding
        """
        parts = [task.title]

        if task.description:
            parts.append(task.description)

        if task.tags:
            parts.append(str(task.tags))

        return "\n".join(parts)

    def index_task(self, task: Task) -> bool:
        """Index or update a task's embedding in the vector store.

        Args:
            task: The task to index

        Returns:
            True if indexing succeeded, False otherwise
        """
        if task.id is None:
            return False

        try:
            conn = self._get_connection()
            content = self._build_task_content(task)
            embedding = self._generate_embedding(content, mode="storage")

            # Upsert into vec_tasks (delete then insert)
            conn.execute("DELETE FROM vec_tasks WHERE task_id = ?", (task.id,))

            # sqlite-vec expects embedding as a blob
            import struct

            embedding_blob = struct.pack(f"{len(embedding)}f", *embedding)

            conn.execute(
                "INSERT INTO vec_tasks (task_id, embedding) VALUES (?, ?)",
                (task.id, embedding_blob),
            )
            conn.commit()
            return True

        except Exception as e:
            print(f"Warning: Failed to index task {task.id}: {e}", file=sys.stderr)
            return False

    def remove_task(self, task_id: int) -> bool:
        """Remove a task's embedding from the vector store.

        Args:
            task_id: The task ID to remove

        Returns:
            True if removal succeeded, False otherwise
        """
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM vec_tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Warning: Failed to remove task {task_id} from index: {e}", file=sys.stderr)
            return False

    def search(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.25,
    ) -> list[tuple[int, float]]:
        """Search for similar tasks using semantic similarity.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0-1, higher is more similar)

        Returns:
            List of (task_id, distance) tuples, sorted by similarity
        """
        try:
            conn = self._get_connection()
            query_embedding = self._generate_embedding(query, mode="query")

            # Pack embedding as blob for sqlite-vec
            import struct

            embedding_blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)

            # Query using vec0 distance function
            cursor = conn.execute(
                """
                SELECT task_id, distance
                FROM vec_tasks
                WHERE embedding MATCH ?
                  AND k = ?
                ORDER BY distance
                """,
                (embedding_blob, limit),
            )

            results = []
            for row in cursor.fetchall():
                task_id, distance = row
                # Convert distance to similarity score (lower distance = higher similarity)
                # vec0 uses L2 distance, we normalize it
                similarity = 1.0 / (1.0 + distance)
                if similarity >= threshold:
                    results.append((task_id, similarity))

            return results

        except Exception as e:
            print(f"Warning: Semantic search failed: {e}", file=sys.stderr)
            return []

    def find_similar(
        self,
        text: str,
        threshold: float = 0.2,
        limit: int = 3,
    ) -> list[tuple[int, float]]:
        """Find tasks similar to the given text (for duplicate detection).

        Uses a stricter threshold for duplicate detection.

        Args:
            text: The text to check for similar existing tasks
            threshold: Similarity threshold (higher = more strict)
            limit: Maximum number of similar tasks to return

        Returns:
            List of (task_id, similarity) tuples
        """
        return self.search(text, limit=limit, threshold=threshold)

    def reindex_all(self, tasks: list[Task]) -> tuple[int, int]:
        """Reindex all tasks for initial migration or repair.

        Args:
            tasks: List of all tasks to index

        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failure = 0

        for task in tasks:
            if self.index_task(task):
                success += 1
            else:
                failure += 1

        return success, failure

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> SemanticSearchService:
        """Context manager entry."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Context manager exit."""
        self.close()


def get_semantic_search_service(profile: str = "default") -> SemanticSearchService:
    """Get a SemanticSearchService instance for a profile.

    Args:
        profile: Database profile to use (default, dev, test)

    Returns:
        SemanticSearchService configured for the profile
    """
    from taskmanager.config import create_settings_for_profile

    settings = create_settings_for_profile(profile)
    db_url = settings.get_database_url()

    # Extract path from sqlite:/// URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url[10:]  # Remove "sqlite:///"
    else:
        db_path = db_url

    return SemanticSearchService(db_path)
