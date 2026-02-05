"""Tests for attachment content retrieval functionality.

Tests for the new attachment content retrieval feature via CLI and MCP,
enabling agents to read prompt files and other attachments directly.
"""

import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from taskmanager.repository_impl import SQLTaskRepository
from taskmanager.service import TaskService


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
def service(session):
    """Create a task service for testing."""
    repository = SQLTaskRepository(session)
    return TaskService(repository)


@pytest.fixture
def task_with_attachment(service):
    """Create a task and attach a test file."""
    task = service.create_task("Test Task", "Description")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Prompt\n\nThis is test content for attachment retrieval.")
        temp_file = Path(f.name)
    
    try:
        metadata = service.add_attachment(task.id, temp_file)
        yield task, metadata, service
    finally:
        if temp_file.exists():
            temp_file.unlink()


class TestServiceGetAttachmentContent:
    """Tests for TaskService.get_attachment_content()"""

    def test_get_attachment_content_success(self, task_with_attachment):
        """Should retrieve existing attachment content."""
        task, metadata, service = task_with_attachment
        
        content = service.get_attachment_content(task.id, metadata["filename"])
        
        assert content is not None
        assert isinstance(content, bytes)
        assert b"Test Prompt" in content
        assert b"test content" in content

    def test_get_attachment_content_not_found(self, service):
        """Should return None for non-existent attachment."""
        task = service.create_task("Empty Task", "No attachments")
        content = service.get_attachment_content(task.id, "nonexistent.md")
        assert content is None

    def test_get_attachment_content_partial_match(self, task_with_attachment):
        """Should find attachment by partial filename match."""
        task, metadata, service = task_with_attachment
        original_name = metadata["original_name"]
        
        content = service.get_attachment_content(task.id, original_name)
        
        assert content is not None
        assert b"Test Prompt" in content

    def test_get_attachment_content_invalid_task(self, service):
        """Should raise error for non-existent task."""
        with pytest.raises(ValueError, match="not found"):
            service.get_attachment_content(9999, "any_file.txt")

    def test_get_attachment_content_multiple_attachments(self, service):
        """Should retrieve correct content from task with multiple attachments."""
        task = service.create_task("Multi-attach Task", "Multiple attachments")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("File 1 content")
            file1 = Path(f.name)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("File 2 content")
            file2 = Path(f.name)
        
        try:
            meta1 = service.add_attachment(task.id, file1)
            meta2 = service.add_attachment(task.id, file2)
            
            content1 = service.get_attachment_content(task.id, meta1["filename"])
            content2 = service.get_attachment_content(task.id, meta2["filename"])
            
            assert content1 is not None
            assert content2 is not None
            assert b"File 1" in content1
            assert b"File 2" in content2
        finally:
            if file1.exists():
                file1.unlink()
            if file2.exists():
                file2.unlink()

    def test_get_attachment_content_binary_file(self, service):
        """Should handle binary files gracefully."""
        task = service.create_task("Binary Task", "Test binary attachment")
        
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'\x00\x01\x02\x03\x04\x05')
            binary_file = Path(f.name)
        
        try:
            metadata = service.add_attachment(task.id, binary_file)
            content = service.get_attachment_content(task.id, metadata["filename"])
            
            assert content is not None
            assert content == b'\x00\x01\x02\x03\x04\x05'
        finally:
            if binary_file.exists():
                binary_file.unlink()

    def test_large_attachment_retrieval(self, service):
        """Should handle large file attachments."""
        task = service.create_task("Large File Task", "Test large attachment")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("x" * (1024 * 1024))  # 1 MB
            large_file = Path(f.name)
        
        try:
            metadata = service.add_attachment(task.id, large_file)
            content = service.get_attachment_content(task.id, metadata["filename"])
            
            assert content is not None
            assert len(content) == (1024 * 1024)
        finally:
            if large_file.exists():
                large_file.unlink()


class TestAttachmentRetrievalIntegration:
    """Integration tests for attachment retrieval workflow"""

    def test_workflow_create_attach_retrieve(self, service):
        """Test complete workflow: create task, attach file, retrieve content."""
        task = service.create_task("Integration Test Task", "Testing workflow")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Integration Test\n\nContent for integration test")
            temp_file = Path(f.name)
        
        try:
            metadata = service.add_attachment(task.id, temp_file)
            content = service.get_attachment_content(task.id, metadata["filename"])
            
            assert content is not None
            assert b"Integration Test" in content
            
            content2 = service.get_attachment_content(task.id, metadata["original_name"])
            assert content2 == content
            
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_error_handling_invalid_task_id(self, service):
        """Should handle invalid task IDs gracefully."""
        with pytest.raises(ValueError):
            service.get_attachment_content(9999, "any.txt")
