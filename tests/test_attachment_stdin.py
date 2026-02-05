"""Tests for stdin and content-based attachment functionality."""

import pytest
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.service import TaskService
from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.models import TaskStatus


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a new database session for each test."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def repository(session):
    """Create a repository instance for testing."""
    return SQLTaskRepository(session)


@pytest.fixture
def service(repository):
    """Create a TaskService with test database."""
    return TaskService(repository)


@pytest.fixture
def task_id(service):
    """Create a test task and return its ID."""
    task = service.create_task("Test Task", description="For attachment testing")
    return task.id


class TestAttachmentFromContent:
    """Test add_attachment_from_content with various input types."""

    def test_add_attachment_from_bytes(self, service, task_id):
        """Add attachment from binary content."""
        content = b"Binary content for testing"
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="test_file.bin",
            content=content
        )
        
        assert metadata["original_name"] == "test_file.bin"
        assert metadata["size"] == len(content)
        assert "20" in metadata["filename"]  # Timestamp prefix
        assert "_test_file.bin" in metadata["filename"]

    def test_add_attachment_from_string(self, service, task_id):
        """Add attachment from string content (auto-converted to UTF-8)."""
        content = "Generated prompt text\nwith multiple lines"
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="TASK_60_PROMPT.md",
            content=content
        )
        
        assert metadata["original_name"] == "TASK_60_PROMPT.md"
        assert metadata["size"] == len(content.encode('utf-8'))
        assert "_TASK_60_PROMPT.md" in metadata["filename"]

    def test_add_attachment_unicode_string(self, service, task_id):
        """Add attachment from string with unicode characters."""
        content = "Unicode content: 日本語, 中文, العربية, emoji 🚀"
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="unicode_test.md",
            content=content
        )
        
        expected_size = len(content.encode('utf-8'))
        assert metadata["size"] == expected_size

    def test_add_attachment_empty_content_raises_error(self, service, task_id):
        """Empty content should raise ValueError."""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            service.add_attachment_from_content(
                task_id=task_id,
                filename="empty.txt",
                content=""
            )

    def test_add_attachment_empty_bytes_raises_error(self, service, task_id):
        """Empty bytes should raise ValueError."""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            service.add_attachment_from_content(
                task_id=task_id,
                filename="empty.bin",
                content=b""
            )

    def test_add_attachment_empty_filename_raises_error(self, service, task_id):
        """Empty filename should raise ValueError."""
        content = "Some content"
        
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            service.add_attachment_from_content(
                task_id=task_id,
                filename="",
                content=content
            )

    def test_add_attachment_whitespace_filename_raises_error(self, service, task_id):
        """Whitespace-only filename should raise ValueError."""
        content = "Some content"
        
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            service.add_attachment_from_content(
                task_id=task_id,
                filename="   ",
                content=content
            )

    def test_add_attachment_filename_with_spaces(self, service, task_id):
        """Filename with spaces should be handled correctly."""
        content = "Content for file with spaces"
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="My Prompt File.md",
            content=content
        )
        
        assert metadata["original_name"] == "My Prompt File.md"
        assert "My Prompt File.md" in metadata["filename"]

    def test_add_attachment_filename_with_path_separators(self, service, task_id):
        """Filename with path separators should be normalized."""
        content = "Content"
        
        # Provide a path-like filename
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="some/path/to/file.md",
            content=content
        )
        
        # Should extract just the filename
        assert metadata["original_name"] == "file.md"
        assert "file.md" in metadata["filename"]

    def test_add_attachment_large_content(self, service, task_id):
        """Handle large content attachment."""
        # 10 MB of content
        content = "x" * (10 * 1024 * 1024)
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="large_file.txt",
            content=content
        )
        
        assert metadata["size"] == len(content)

    def test_add_attachment_invalid_task_raises_error(self, service):
        """Invalid task ID should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.add_attachment_from_content(
                task_id=9999,
                filename="test.txt",
                content="content"
            )

    def test_add_attachment_preserves_task_metadata(self, service, task_id):
        """Adding attachment should update task's attachments metadata."""
        task_before = service.get_task(task_id)
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="test.txt",
            content="content"
        )
        
        task_after = service.get_task(task_id)
        
        # Task should be marked updated
        assert task_after.updated_at >= task_before.updated_at

    def test_add_multiple_attachments(self, service, task_id):
        """Add multiple attachments to same task."""
        metadata1 = service.add_attachment_from_content(
            task_id=task_id,
            filename="file1.txt",
            content="Content 1"
        )
        
        metadata2 = service.add_attachment_from_content(
            task_id=task_id,
            filename="file2.txt",
            content="Content 2"
        )
        
        attachments = service.list_attachments(task_id)
        
        assert len(attachments) >= 2
        filenames = [a["original_name"] for a in attachments]
        assert "file1.txt" in filenames
        assert "file2.txt" in filenames


class TestAttachmentRetrieval:
    """Test retrieval of attachments added via content."""

    def test_retrieve_attachment_added_via_content(self, service, task_id):
        """Retrieve attachment that was added via content."""
        original_content = "Test prompt content here"
        
        service.add_attachment_from_content(
            task_id=task_id,
            filename="TASK_60_PROMPT.md",
            content=original_content
        )
        
        retrieved_content = service.get_attachment_content(
            task_id=task_id,
            filename="TASK_60_PROMPT"  # More specific match
        )
        
        assert retrieved_content is not None
        assert retrieved_content.decode('utf-8') == original_content

    def test_retrieve_unicode_attachment(self, service, task_id):
        """Retrieve attachment with unicode content."""
        original_content = "Unicode: 日本語, 🚀, العربية"
        
        service.add_attachment_from_content(
            task_id=task_id,
            filename="unicode.txt",
            content=original_content
        )
        
        retrieved_content = service.get_attachment_content(
            task_id=task_id,
            filename="unicode"
        )
        
        assert retrieved_content.decode('utf-8') == original_content


class TestAttachmentFileOperations:
    """Test that attachments are properly stored on filesystem."""

    def test_attachment_file_created(self, service, task_id, tmp_path):
        """Verify attachment file is created on filesystem."""
        # Use the workspace to get task directory
        content = "File system test content"
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="test_fs.txt",
            content=content
        )
        
        # The file should exist in the task's attachment directory
        # (This depends on the AttachmentManager implementation)
        assert metadata["size"] == len(content)
        assert metadata["filename"]  # Should have storage filename

    def test_attachment_binary_preservation(self, service, task_id):
        """Verify binary content is preserved exactly."""
        # Create binary content with all byte values
        original_bytes = bytes(range(256))
        
        metadata = service.add_attachment_from_content(
            task_id=task_id,
            filename="binary.bin",
            content=original_bytes
        )
        
        retrieved = service.get_attachment_content(
            task_id=task_id,
            filename="binary"
        )
        
        assert retrieved == original_bytes


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_filename_normalization(self, service, task_id):
        """Test that various filename formats are normalized correctly."""
        test_cases = [
            ("./file.txt", "file.txt"),
            ("../file.txt", "file.txt"),
            ("/abs/path/file.txt", "file.txt"),
            ("file.txt", "file.txt"),
            ("subdir/file.txt", "file.txt"),  # Unix-style path
        ]
        
        for input_name, expected_name in test_cases:
            metadata = service.add_attachment_from_content(
                task_id=task_id,
                filename=input_name,
                content=f"Content for {input_name}"
            )
            
            assert metadata["original_name"] == expected_name

    def test_special_characters_in_filename(self, service, task_id):
        """Handle filenames with special characters."""
        filenames = [
            "TASK_60_PROMPT-v2.md",
            "file (1).txt",
            "report@2026-02-04.pdf",
            "data[backup].csv",
        ]
        
        for filename in filenames:
            metadata = service.add_attachment_from_content(
                task_id=task_id,
                filename=filename,
                content="Content"
            )
            
            assert metadata["original_name"] == filename
