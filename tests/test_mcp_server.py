"""Unit tests for MCP server status mapping functions."""

import pytest

from taskmanager.models import TaskStatus
from mcp_server.server import mcp_status_to_task_status, task_status_to_mcp_status


class TestStatusMapping:
    """Test status conversion between MCP and TaskStatus."""

    def test_mcp_todo_to_pending(self):
        """Test that 'todo' maps to PENDING."""
        assert mcp_status_to_task_status("todo") == TaskStatus.PENDING

    def test_mcp_pending_to_pending(self):
        """Test that 'pending' also maps to PENDING (direct use)."""
        assert mcp_status_to_task_status("pending") == TaskStatus.PENDING

    def test_mcp_in_progress_to_in_progress(self):
        """Test that 'in_progress' maps to IN_PROGRESS."""
        assert mcp_status_to_task_status("in_progress") == TaskStatus.IN_PROGRESS

    def test_mcp_done_to_completed(self):
        """Test that 'done' maps to COMPLETED."""
        assert mcp_status_to_task_status("done") == TaskStatus.COMPLETED

    def test_mcp_completed_to_completed(self):
        """Test that 'completed' also maps to COMPLETED (direct use)."""
        assert mcp_status_to_task_status("completed") == TaskStatus.COMPLETED

    def test_mcp_cancelled_to_cancelled(self):
        """Test that 'cancelled' maps to CANCELLED."""
        assert mcp_status_to_task_status("cancelled") == TaskStatus.CANCELLED

    def test_mcp_archived_to_archived(self):
        """Test that 'archived' maps to ARCHIVED."""
        assert mcp_status_to_task_status("archived") == TaskStatus.ARCHIVED

    def test_invalid_status_raises_error(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status 'invalid'"):
            mcp_status_to_task_status("invalid")

    def test_reverse_mapping_pending_to_todo(self):
        """Test that PENDING maps back to 'todo'."""
        assert task_status_to_mcp_status(TaskStatus.PENDING) == "todo"

    def test_reverse_mapping_in_progress(self):
        """Test that IN_PROGRESS maps back to 'in_progress'."""
        assert task_status_to_mcp_status(TaskStatus.IN_PROGRESS) == "in_progress"

    def test_reverse_mapping_completed_to_done(self):
        """Test that COMPLETED maps back to 'done'."""
        assert task_status_to_mcp_status(TaskStatus.COMPLETED) == "done"

    def test_reverse_mapping_cancelled(self):
        """Test that CANCELLED maps back to 'cancelled'."""
        assert task_status_to_mcp_status(TaskStatus.CANCELLED) == "cancelled"

    def test_reverse_mapping_archived(self):
        """Test that ARCHIVED maps back to 'archived'."""
        assert task_status_to_mcp_status(TaskStatus.ARCHIVED) == "archived"

    def test_bidirectional_consistency(self):
        """Test that forward and reverse mappings are consistent."""
        # Test all TaskStatus values can round-trip
        for task_status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED,
                           TaskStatus.CANCELLED, TaskStatus.ARCHIVED]:
            mcp_status = task_status_to_mcp_status(task_status)
            assert mcp_status_to_task_status(mcp_status) == task_status

    def test_all_mcp_aliases_work(self):
        """Test that all advertised MCP status values work."""
        # These are the values advertised in Literal types
        valid_statuses = ["todo", "in_progress", "done", "cancelled", "archived"]
        
        for status in valid_statuses:
            # Should not raise any exception
            result = mcp_status_to_task_status(status)
            assert isinstance(result, TaskStatus)

    def test_case_sensitivity(self):
        """Test that status mapping is case-sensitive."""
        with pytest.raises(ValueError):
            mcp_status_to_task_status("TODO")
        
        with pytest.raises(ValueError):
            mcp_status_to_task_status("Done")
