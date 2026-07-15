#!/usr/bin/env python3
"""Test for worktree path boundary enforcement (Issue #1390).

Tests that Write/Edit operations from within batch worktrees cannot
escape to write outside the worktree boundary.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the hooks directory to path for imports
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "plugins/autonomous-dev/hooks"))

# Import the module so we can patch it correctly
import unified_pre_tool
from unified_pre_tool import _check_worktree_path_boundary


class TestWorktreePathBoundary:
    """Test the worktree path boundary check function."""

    def test_non_worktree_mode_allows_all(self):
        """In non-worktree mode, all paths are allowed."""
        # Mock getcwd to return non-worktree path
        with patch('unified_pre_tool.os.getcwd', return_value='/home/user/project'):
            # Write tool
            result = _check_worktree_path_boundary(
                "Write",
                {"file_path": "/tmp/test.txt", "content": "test"}
            )
            assert result is None, "Should allow writes in non-worktree mode"
            
            # Edit tool
            result = _check_worktree_path_boundary(
                "Edit",
                {"file_path": "/etc/config", "old_string": "a", "new_string": "b"}
            )
            assert result is None, "Should allow edits in non-worktree mode"

    def test_worktree_mode_allows_internal_paths(self):
        """In worktree mode, paths within worktree are allowed."""
        worktree_path = "/home/user/project/.worktrees/batch-123"
        
        with patch('unified_pre_tool.os.getcwd', return_value=worktree_path):
            # Absolute path within worktree
            result = _check_worktree_path_boundary(
                "Write",
                {"file_path": f"{worktree_path}/src/file.py", "content": "code"}
            )
            assert result is None, "Should allow absolute paths within worktree"
            
            # Relative path (resolves within worktree)
            with patch.object(unified_pre_tool.Path, 'resolve') as mock_resolve:
                def resolve_side_effect(self):
                    path_str = str(self)
                    if path_str == "src/file.py":
                        return Path(f"{worktree_path}/src/file.py")
                    elif path_str == worktree_path or path_str.startswith("/home/user/project/.worktrees/batch-"):
                        return Path(path_str)
                    return Path(path_str) if path_str.startswith("/") else Path(worktree_path) / path_str
                
                mock_resolve.side_effect = resolve_side_effect
                result = _check_worktree_path_boundary(
                    "Edit",
                    {"file_path": "src/file.py", "old_string": "a", "new_string": "b"}
                )
                assert result is None, "Should allow relative paths within worktree"

    def test_worktree_mode_blocks_external_paths(self):
        """In worktree mode, paths outside worktree are blocked."""
        worktree_path = "/home/user/project/.worktrees/batch-123"
        
        with patch('unified_pre_tool.os.getcwd', return_value=worktree_path):
            # Absolute path outside worktree
            result = _check_worktree_path_boundary(
                "Write",
                {"file_path": "/home/user/project/README.md", "content": "text"}
            )
            assert result is not None, "Should block absolute paths outside worktree"
            assert len(result) == 2, "Should return (path, reason) tuple"
            path, reason = result
            assert path == "/home/user/project/README.md"
            assert "WORKTREE BOUNDARY VIOLATION" in reason
            assert "Issue #1390" in reason
            
            # Path to parent directory - need to return unified_pre_tool.Path objects
            original_resolve = unified_pre_tool.Path.resolve
            
            def mock_resolve(self):
                path_str = str(self)
                # If it's our test path, return the escaped path
                if path_str == "../../main.py":
                    return unified_pre_tool.Path("/home/user/project/main.py")
                # If it's the worktree path, return it resolved
                elif path_str == worktree_path:
                    return unified_pre_tool.Path(path_str)
                # Default case - use original resolve
                else:
                    return original_resolve(self)
            
            with patch.object(unified_pre_tool.Path, 'resolve', mock_resolve):
                result = _check_worktree_path_boundary(
                    "Edit",
                    {"file_path": "../../main.py", "old_string": "a", "new_string": "b"}
                )
                assert result is not None, "Should block relative paths escaping worktree"
                path, reason = result
                assert "WORKTREE BOUNDARY VIOLATION" in reason

    def test_worktree_nested_paths(self):
        """Test nested worktree detection works correctly."""
        # Simulate being deep inside a worktree
        deep_path = "/home/user/project/.worktrees/batch-456/src/lib/utils"
        worktree_root = "/home/user/project/.worktrees/batch-456"
        
        with patch('unified_pre_tool.os.getcwd', return_value=deep_path):
            # Path within worktree - should be allowed
            with patch.object(unified_pre_tool.Path, 'resolve') as mock_resolve:
                def resolve_side_effect(self):
                    if str(self) == "test.py":
                        return Path(f"{worktree_root}/src/lib/utils/test.py")
                    elif str(self) == deep_path:
                        return Path(deep_path)
                    return Path(str(self))
                
                mock_resolve.side_effect = resolve_side_effect
                
                result = _check_worktree_path_boundary(
                    "Write",
                    {"file_path": "test.py", "content": "code"}
                )
                assert result is None, "Should allow files within nested worktree path"

    def test_non_write_edit_tools_ignored(self):
        """Non-Write/Edit tools should be ignored by this check."""
        worktree_path = "/home/user/project/.worktrees/batch-789"
        
        with patch('unified_pre_tool.os.getcwd', return_value=worktree_path):
            # Bash tool - should not be checked
            result = _check_worktree_path_boundary(
                "Bash",
                {"command": "rm -rf /"}
            )
            assert result is None, "Should not check Bash commands"
            
            # Read tool - should not be checked
            result = _check_worktree_path_boundary(
                "Read",
                {"file_path": "/etc/passwd"}
            )
            assert result is None, "Should not check Read operations"

    def test_empty_file_path_handled(self):
        """Empty or missing file paths should be handled gracefully."""
        worktree_path = "/home/user/project/.worktrees/batch-999"
        
        with patch('unified_pre_tool.os.getcwd', return_value=worktree_path):
            # Empty file_path
            result = _check_worktree_path_boundary(
                "Write",
                {"file_path": "", "content": "test"}
            )
            assert result is None, "Should handle empty file_path"
            
            # Missing file_path key
            result = _check_worktree_path_boundary(
                "Edit",
                {"old_string": "a", "new_string": "b"}
            )
            assert result is None, "Should handle missing file_path key"

    def test_exception_handling(self):
        """Exceptions during checks should fail open (allow)."""
        worktree_path = "/home/user/project/.worktrees/batch-error"
        
        with patch('unified_pre_tool.os.getcwd', return_value=worktree_path):
            # Mock Path.resolve to raise exception
            with patch.object(unified_pre_tool.Path, 'resolve', side_effect=Exception("Test error")):
                result = _check_worktree_path_boundary(
                    "Write",
                    {"file_path": "/tmp/file.txt", "content": "test"}
                )
                assert result is None, "Should fail open on exceptions"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])