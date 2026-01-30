"""Tests for @FILENAME file loading feature."""

import os
import tempfile
from pathlib import Path
import pytest
from typer.testing import CliRunner
from taskmanager.cli import app


@pytest.fixture
def runner():
    """Create a CLI runner with isolated temporary filesystem."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a temporary database in the isolated filesystem
        os.environ['TASK_MANAGER_PROFILE'] = 'test'
        os.environ['TASK_MANAGER_CONFIG_DIR'] = os.getcwd()
        
        # Create config directory structure
        config_dir = Path(os.getcwd()) / '.taskmanager'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test profile config
        profile_dir = config_dir / 'profiles' / 'test'
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a minimal config file
        config_file = profile_dir / 'config.toml'
        config_file.write_text('[database]\npath = "tasks.db"\n')
        
        yield runner
        
        # Cleanup environment
        os.environ.pop('TASK_MANAGER_PROFILE', None)
        os.environ.pop('TASK_MANAGER_CONFIG_DIR', None)


@pytest.fixture
def test_file():
    """Create a temporary test file with content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is test content\nwith multiple lines\nfor testing file loading.")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_add_task_with_file_description(runner, test_file):
    """Test adding a task with description loaded from file."""
    result = runner.invoke(app, [
        'add',
        'Test task with file',
        '--description', f'@{test_file}',
        '--priority', 'medium'
    ])
    
    assert result.exit_code == 0
    assert "Test task with file" in result.output
    
    # Verify the content was loaded
    list_result = runner.invoke(app, ['show', '1'])
    assert "This is test content" in list_result.output
    assert "with multiple lines" in list_result.output


def test_add_task_with_regular_description(runner):
    """Test that regular descriptions (without @) still work."""
    result = runner.invoke(app, [
        'add',
        'Regular task',
        '--description', 'Just a regular description',
        '--priority', 'low'
    ])
    
    assert result.exit_code == 0
    assert "Regular task" in result.output


def test_add_task_with_literal_at_sign(runner):
    """Test description starting with @ but not a file path."""
    result = runner.invoke(app, [
        'add',
        'Task with @mention',
        '--description', '@user mention in the description',
        '--priority', 'low'
    ])
    
    # Should treat as literal text since it's not a valid file path
    assert result.exit_code == 0


def test_update_task_with_file_description(runner, test_file):
    """Test updating a task description from a file."""
    # First create a task
    runner.invoke(app, ['add', 'Task to update', '--priority', 'low'])
    
    # Update with file content
    result = runner.invoke(app, [
        'update',
        '1',
        '--description', f'@{test_file}'
    ])
    
    assert result.exit_code == 0
    
    # Verify the content was updated
    show_result = runner.invoke(app, ['show', '1'])
    assert "This is test content" in show_result.output


def test_file_not_found_error(runner):
    """Test error handling for non-existent files."""
    result = runner.invoke(app, [
        'add',
        'Task with bad file',
        '--description', '@/nonexistent/path/to/file.txt',
        '--priority', 'low'
    ])
    
    assert result.exit_code != 0
    assert "File not found" in result.output


def test_file_with_special_characters(runner):
    """Test loading file with special characters in content."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Special chars: $VAR, ${INTERPOLATION}, `backticks`, \"quotes\"")
        temp_path = f.name
    
    try:
        result = runner.invoke(app, [
            'add',
            'Task with special chars',
            '--description', f'@{temp_path}',
            '--priority', 'low'
        ])
        
        assert result.exit_code == 0
        
        show_result = runner.invoke(app, ['show', '1'])
        assert "$VAR" in show_result.output
        assert "backticks" in show_result.output
    finally:
        os.unlink(temp_path)


def test_empty_file(runner):
    """Test loading an empty file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        # Write nothing
        temp_path = f.name
    
    try:
        result = runner.invoke(app, [
            'add',
            'Task with empty file',
            '--description', f'@{temp_path}',
            '--priority', 'low'
        ])
        
        assert result.exit_code == 0
    finally:
        os.unlink(temp_path)


def test_relative_path_file(runner):
    """Test loading file with relative path."""
    # Create a file in current directory
    test_content = "Relative path test content"
    with open('test_relative.txt', 'w') as f:
        f.write(test_content)
    
    try:
        result = runner.invoke(app, [
            'add',
            'Task with relative path',
            '--description', '@test_relative.txt',
            '--priority', 'low'
        ])
        
        assert result.exit_code == 0
        
        show_result = runner.invoke(app, ['show', '1'])
        assert test_content in show_result.output
    finally:
        if os.path.exists('test_relative.txt'):
            os.unlink('test_relative.txt')


def test_tilde_expansion(runner):
    """Test that ~ is expanded in file paths."""
    # Create a file in home directory
    home = Path.home()
    test_file = home / 'test_tilde_expansion.txt'
    test_content = "Tilde expansion test"
    
    test_file.write_text(test_content)
    
    try:
        result = runner.invoke(app, [
            'add',
            'Task with tilde path',
            '--description', f'@~/test_tilde_expansion.txt',
            '--priority', 'low'
        ])
        
        assert result.exit_code == 0
        
        show_result = runner.invoke(app, ['show', '1'])
        assert test_content in show_result.output
    finally:
        test_file.unlink()
