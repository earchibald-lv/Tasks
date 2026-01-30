"""File attachment management for tasks.

This module handles file attachments for tasks, including storage,
retrieval, and metadata management.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class AttachmentMetadata(TypedDict):
    """Metadata for a file attachment."""
    
    filename: str
    original_name: str
    size: int
    added_at: str
    mime_type: str | None


class AttachmentManager:
    """Manages file attachments for tasks."""
    
    def __init__(self, base_dir: Path | None = None):
        """Initialize attachment manager.
        
        Args:
            base_dir: Base directory for attachments. If None, uses system-specific default.
        """
        if base_dir is None:
            base_dir = self._get_default_base_dir()
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _get_default_base_dir() -> Path:
        """Get the default base directory for attachments.
        
        Returns system-specific documents directory:
        - macOS/Linux: ~/Documents/TaskManager/attachments
        - Windows: ~\\Documents\\TaskManager\\attachments
        """
        return Path.home() / "Documents" / "TaskManager" / "attachments"
    
    def get_task_dir(self, task_id: int) -> Path:
        """Get the directory for a specific task's attachments.
        
        Args:
            task_id: The task ID
            
        Returns:
            Path to the task's attachment directory
        """
        task_dir = self.base_dir / f"task_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
    
    def add_attachment(
        self,
        task_id: int,
        source_path: Path,
        mime_type: str | None = None
    ) -> AttachmentMetadata:
        """Add a file attachment to a task.
        
        Args:
            task_id: The task ID
            source_path: Path to the file to attach
            mime_type: Optional MIME type of the file
            
        Returns:
            Metadata for the added attachment
            
        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If source is not a file
        """
        source = Path(source_path)
        
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")
        
        if not source.is_file():
            raise ValueError(f"Not a file: {source}")
        
        # Create task directory
        task_dir = self.get_task_dir(task_id)
        
        # Generate unique filename to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{source.name}"
        dest_path = task_dir / filename
        
        # Copy the file
        shutil.copy2(source, dest_path)
        
        # Create metadata
        metadata: AttachmentMetadata = {
            "filename": filename,
            "original_name": source.name,
            "size": dest_path.stat().st_size,
            "added_at": datetime.now().isoformat(),
            "mime_type": mime_type
        }
        
        return metadata
    
    def remove_attachment(self, task_id: int, filename: str) -> bool:
        """Remove a file attachment from a task.
        
        Args:
            task_id: The task ID
            filename: The filename of the attachment to remove
            
        Returns:
            True if file was removed, False if not found
        """
        task_dir = self.get_task_dir(task_id)
        file_path = task_dir / filename
        
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        
        return False
    
    def get_attachment_path(self, task_id: int, filename: str) -> Path:
        """Get the full path to an attachment file.
        
        Args:
            task_id: The task ID
            filename: The filename of the attachment
            
        Returns:
            Full path to the attachment file
        """
        return self.get_task_dir(task_id) / filename
    
    def list_attachments(self, task_id: int) -> list[Path]:
        """List all attachment files for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of paths to attachment files
        """
        task_dir = self.get_task_dir(task_id)
        
        if not task_dir.exists():
            return []
        
        return [f for f in task_dir.iterdir() if f.is_file()]
    
    def cleanup_task_attachments(self, task_id: int) -> int:
        """Remove all attachments for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            Number of files removed
        """
        task_dir = self.get_task_dir(task_id)
        
        if not task_dir.exists():
            return 0
        
        count = 0
        for file_path in task_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
                count += 1
        
        # Remove the directory if empty
        try:
            task_dir.rmdir()
        except OSError:
            pass  # Directory not empty or other error
        
        return count


def parse_attachments(attachments_json: str | None) -> list[AttachmentMetadata]:
    """Parse attachments JSON string to list of metadata.
    
    Args:
        attachments_json: JSON string of attachment metadata
        
    Returns:
        List of attachment metadata dictionaries
    """
    if not attachments_json:
        return []
    
    try:
        data = json.loads(attachments_json)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def serialize_attachments(attachments: list[AttachmentMetadata]) -> str | None:
    """Serialize attachment metadata to JSON string.
    
    Args:
        attachments: List of attachment metadata
        
    Returns:
        JSON string or None if list is empty
    """
    if not attachments:
        return None
    
    return json.dumps(attachments)
