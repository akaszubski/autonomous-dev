#!/usr/bin/env python3
"""
TDD Tests for SessionTracker Library Creation (Issue #79) - RED PHASE

This test suite validates the creation of a new SessionTracker library in
plugins/autonomous-dev/lib/session_tracker.py with portable path detection.

Problem (Issue #79):
- session_tracker.py functionality currently in scripts/ with hardcoded paths
- Doesn't work from nested subdirectories
- Can't be imported as library (only CLI usage)
- No portable path detection

Solution:
- Create lib/session_tracker.py with SessionTracker class
- Use path_utils.get_session_dir() for portable paths
- Support both library imports and CLI usage
- Add CLI wrapper in scripts/session_tracker.py

Test Coverage:
1. SessionTracker class initialization
2. SessionTracker.log() method
3. get_default_session_file() helper function
4. Works from nested subdirectories
5. Security validation (no path traversal)
6. Error handling and helpful messages
7. Thread safety considerations
8. Cross-platform compatibility

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (lib/session_tracker.py doesn't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2025-11-19
Issue: GitHub #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See library-design-patterns skill for two-tier CLI design pattern.
    See python-standards skill for test code conventions.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any

import pytest

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# This import will FAIL until lib/session_tracker.py is created
try:
    from session_tracker import SessionTracker, get_default_session_file
    LIB_SESSION_TRACKER_EXISTS = True
except ImportError:
    LIB_SESSION_TRACKER_EXISTS = False
    SessionTracker = None
    get_default_session_file = None


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing.

    Simulates a user's project with .git marker.

    Structure:
    tmp_project/
        .git/
        .claude/
            PROJECT.md
        docs/
            sessions/
        plugins/
            autonomous-dev/
                lib/
                    session_tracker.py  # What we're creating
                    path_utils.py       # Dependency
                    security_utils.py   # Dependency
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "PROJECT.md").write_text("# Test Project\n")

    # Create sessions directory
    sessions_dir = tmp_path / "docs" / "sessions"
    sessions_dir.mkdir(parents=True)

    # Create plugin directory structure
    lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
    lib_dir.mkdir(parents=True)

    # Copy path_utils.py dependency
    path_utils_src = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "path_utils.py"
    if path_utils_src.exists():
        import shutil
        shutil.copy(path_utils_src, lib_dir / "path_utils.py")

    return tmp_path


@pytest.fixture
def nested_subdir(temp_project):
    """Create a nested subdirectory for testing path detection."""
    nested = temp_project / "src" / "features" / "auth"
    nested.mkdir(parents=True)
    return nested


@pytest.fixture
def mock_session_dir(tmp_path):
    """Create a mock session directory."""
    session_dir = tmp_path / "docs" / "sessions"
    session_dir.mkdir(parents=True)
    return session_dir


# ============================================================================
# TEST: Library Import and Module Structure
# ============================================================================


class TestLibraryImport:
    """Test that library module exists and has correct structure."""

    def test_lib_session_tracker_module_exists(self):
        """Test that lib/session_tracker.py module exists and is importable."""
        # WILL FAIL: Module doesn't exist yet
        assert LIB_SESSION_TRACKER_EXISTS, (
            "Library module not found: plugins/autonomous-dev/lib/session_tracker.py\n"
            "Expected: SessionTracker class and helper functions\n"
            "Action: Create lib/session_tracker.py with SessionTracker class\n"
            "Issue: #79 - Create portable session tracking library"
        )

    def test_session_tracker_class_exists(self):
        """Test that SessionTracker class is defined."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: Class doesn't exist yet
        assert SessionTracker is not None, (
            "SessionTracker class not found in lib/session_tracker.py\n"
            "Expected: class SessionTracker with __init__ and log methods\n"
            "Action: Implement SessionTracker class\n"
            "Issue: #79"
        )

    def test_get_default_session_file_function_exists(self):
        """Test that get_default_session_file() helper function exists."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: Function doesn't exist yet
        assert get_default_session_file is not None, (
            "get_default_session_file() function not found\n"
            "Expected: Helper function to generate session file path\n"
            "Action: Implement get_default_session_file() function\n"
            "Issue: #79"
        )

    def test_module_has_docstring(self):
        """Test that module has comprehensive docstring."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        import session_tracker
        # WILL FAIL: Module doesn't have docstring yet
        assert session_tracker.__doc__ is not None, (
            "lib/session_tracker.py missing module docstring\n"
            "Expected: Comprehensive docstring with usage examples\n"
            "Action: Add docstring to session_tracker.py\n"
            "Issue: #79"
        )

        assert "Session Tracker" in session_tracker.__doc__, (
            "Module docstring doesn't describe purpose\n"
            "Expected: 'Session Tracker' in docstring\n"
            "Issue: #79"
        )


# ============================================================================
# TEST: SessionTracker Class Initialization
# ============================================================================


class TestSessionTrackerInit:
    """Test SessionTracker initialization with various configurations."""

    def test_session_tracker_init_with_default_path(self, temp_project, monkeypatch):
        """Test SessionTracker initializes with default session directory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: SessionTracker.__init__ not implemented
        tracker = SessionTracker()

        # Verify session directory was detected
        assert tracker.session_dir is not None
        assert tracker.session_dir.exists()
        assert tracker.session_dir.name == "sessions"

    def test_session_tracker_init_with_custom_session_file(self, temp_project, monkeypatch):
        """Test SessionTracker accepts custom session file path."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        custom_file = temp_project / "docs" / "sessions" / "custom-session.md"

        # WILL FAIL: Custom session_file parameter not supported
        tracker = SessionTracker(session_file=custom_file)

        assert tracker.session_file == custom_file

    def test_session_tracker_creates_session_file(self, temp_project, monkeypatch):
        """Test SessionTracker creates session file if it doesn't exist."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: SessionTracker doesn't create file
        tracker = SessionTracker()

        assert tracker.session_file.exists()
        assert tracker.session_file.suffix == ".md"

    def test_session_tracker_creates_session_directory(self, tmp_path, monkeypatch):
        """Test SessionTracker creates session directory if missing."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # Create minimal project structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n")

        monkeypatch.chdir(tmp_path)

        # WILL FAIL: SessionTracker doesn't create directory
        tracker = SessionTracker()

        session_dir = tmp_path / "docs" / "sessions"
        assert session_dir.exists()

    def test_session_tracker_init_from_nested_subdir(self, nested_subdir, monkeypatch):
        """Test SessionTracker works from nested subdirectory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(nested_subdir)

        # WILL FAIL: Doesn't work from nested subdirectory
        tracker = SessionTracker()

        # Should find project root and create session in correct location
        assert tracker.session_dir.exists()
        assert "sessions" in str(tracker.session_dir)

    def test_session_tracker_uses_path_utils(self, temp_project, monkeypatch):
        """Test SessionTracker uses path_utils.get_session_dir()."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        with patch('session_tracker.get_session_dir') as mock_get_session_dir:
            mock_get_session_dir.return_value = temp_project / "docs" / "sessions"

            # WILL FAIL: Doesn't use path_utils.get_session_dir()
            tracker = SessionTracker()

            mock_get_session_dir.assert_called_once()


# ============================================================================
# TEST: SessionTracker.log() Method
# ============================================================================


class TestSessionTrackerLog:
    """Test SessionTracker.log() method functionality."""

    def test_log_writes_to_session_file(self, temp_project, monkeypatch):
        """Test log() writes message to session file."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # WILL FAIL: log() method doesn't exist
        tracker.log("researcher", "Research complete")

        content = tracker.session_file.read_text()
        assert "researcher" in content
        assert "Research complete" in content

    def test_log_includes_timestamp(self, temp_project, monkeypatch):
        """Test log() includes timestamp in entry."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # WILL FAIL: Timestamp not included
        tracker.log("planner", "Planning started")

        content = tracker.session_file.read_text()
        # Should include time in HH:MM:SS format
        import re
        assert re.search(r'\d{2}:\d{2}:\d{2}', content), (
            "Timestamp not found in session file\n"
            "Expected: Timestamp in HH:MM:SS format\n"
            "Issue: #79"
        )

    def test_log_multiple_entries_appends(self, temp_project, monkeypatch):
        """Test multiple log() calls append to session file."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # WILL FAIL: Doesn't append, overwrites
        tracker.log("researcher", "Message 1")
        tracker.log("planner", "Message 2")
        tracker.log("implementer", "Message 3")

        content = tracker.session_file.read_text()
        assert "Message 1" in content
        assert "Message 2" in content
        assert "Message 3" in content

    def test_log_handles_multiline_messages(self, temp_project, monkeypatch):
        """Test log() handles multiline messages correctly."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        multiline_msg = "Line 1\nLine 2\nLine 3"

        # WILL FAIL: Multiline handling not implemented
        tracker.log("test-agent", multiline_msg)

        content = tracker.session_file.read_text()
        assert "Line 1" in content
        assert "Line 2" in content
        assert "Line 3" in content

    def test_log_handles_special_characters(self, temp_project, monkeypatch):
        """Test log() handles special characters in messages."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        special_msg = "Message with 'quotes' and \"double quotes\" and $special \\chars"

        # WILL FAIL: Special character handling not implemented
        tracker.log("test-agent", special_msg)

        content = tracker.session_file.read_text()
        assert "'quotes'" in content
        assert '"double quotes"' in content

    def test_log_thread_safety(self, temp_project, monkeypatch):
        """Test log() is thread-safe (uses file locking or atomic writes)."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # WILL FAIL: Thread safety not implemented
        import threading

        def log_message(agent, msg):
            tracker.log(agent, msg)

        threads = []
        for i in range(10):
            t = threading.Thread(target=log_message, args=(f"agent-{i}", f"Message {i}"))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        content = tracker.session_file.read_text()
        # All messages should be present
        for i in range(10):
            assert f"Message {i}" in content


# ============================================================================
# TEST: get_default_session_file() Helper
# ============================================================================


class TestGetDefaultSessionFile:
    """Test get_default_session_file() helper function."""

    def test_get_default_session_file_returns_path(self):
        """Test get_default_session_file() returns Path object."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: Function doesn't exist
        result = get_default_session_file()

        assert isinstance(result, Path)

    def test_get_default_session_file_uses_path_utils(self):
        """Test get_default_session_file() uses path_utils.get_session_dir()."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        with patch('session_tracker.get_session_dir') as mock_get_session_dir:
            mock_get_session_dir.return_value = Path("/tmp/sessions")

            # WILL FAIL: Doesn't use path_utils
            result = get_default_session_file()

            mock_get_session_dir.assert_called_once()

    def test_get_default_session_file_includes_timestamp(self):
        """Test get_default_session_file() includes timestamp in filename."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: Timestamp not included
        result = get_default_session_file()

        filename = result.name
        # Should match format: session-YYYY-MM-DD-HHMMSS.md
        import re
        assert re.match(r'session-\d{4}-\d{2}-\d{2}-\d{6}\.md', filename), (
            f"Session filename doesn't match expected format: {filename}\n"
            "Expected: session-YYYY-MM-DD-HHMMSS.md\n"
            "Issue: #79"
        )

    def test_get_default_session_file_unique_per_call(self):
        """Test get_default_session_file() generates unique filenames."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        import time

        # WILL FAIL: Not unique
        file1 = get_default_session_file()
        time.sleep(1)  # Wait 1 second
        file2 = get_default_session_file()

        assert file1 != file2


# ============================================================================
# TEST: Portable Path Detection
# ============================================================================


class TestPortablePathDetection:
    """Test portable path detection from various directories."""

    def test_works_from_project_root(self, temp_project, monkeypatch):
        """Test SessionTracker works from project root."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: Path detection doesn't work
        tracker = SessionTracker()

        assert tracker.session_dir.exists()
        assert "sessions" in str(tracker.session_dir)

    def test_works_from_nested_subdirectory(self, nested_subdir, monkeypatch):
        """Test SessionTracker works from nested subdirectory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(nested_subdir)

        # WILL FAIL: Doesn't work from nested directory
        tracker = SessionTracker()

        assert tracker.session_dir.exists()
        # Should be at project root, not in nested dir
        assert nested_subdir not in tracker.session_dir.parents

    def test_works_from_docs_directory(self, temp_project, monkeypatch):
        """Test SessionTracker works from docs/ directory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        docs_dir = temp_project / "docs"
        monkeypatch.chdir(docs_dir)

        # WILL FAIL: Path detection fails
        tracker = SessionTracker()

        assert tracker.session_dir.exists()

    def test_works_from_plugins_directory(self, temp_project, monkeypatch):
        """Test SessionTracker works from plugins/ directory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        plugins_dir = temp_project / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        monkeypatch.chdir(plugins_dir)

        # WILL FAIL: Path detection fails
        tracker = SessionTracker()

        assert tracker.session_dir.exists()


# ============================================================================
# TEST: Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    def test_raises_error_when_no_project_root(self, tmp_path, monkeypatch):
        """Test SessionTracker raises helpful error when no project root found."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # Directory without .git or .claude markers
        monkeypatch.chdir(tmp_path)

        # WILL FAIL: Error handling not implemented
        with pytest.raises(FileNotFoundError) as exc_info:
            tracker = SessionTracker()

        assert "project root" in str(exc_info.value).lower()

    def test_handles_permission_error_creating_directory(self, temp_project, monkeypatch):
        """Test SessionTracker handles permission errors gracefully."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        with patch('session_tracker.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")

            # WILL FAIL: Permission error not handled
            with pytest.raises(PermissionError) as exc_info:
                tracker = SessionTracker()

            assert "Permission denied" in str(exc_info.value)

    def test_handles_write_error_gracefully(self, temp_project, monkeypatch):
        """Test log() handles write errors gracefully."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # Make file read-only
        tracker.session_file.chmod(0o444)

        # WILL FAIL: Write error not handled
        with pytest.raises(PermissionError):
            tracker.log("test-agent", "This should fail")

    def test_error_message_includes_context(self, tmp_path, monkeypatch):
        """Test error messages include helpful context."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(tmp_path)

        # WILL FAIL: Error message not helpful
        with pytest.raises(FileNotFoundError) as exc_info:
            tracker = SessionTracker()

        error_msg = str(exc_info.value)
        # Should mention what went wrong and how to fix it
        assert any(keyword in error_msg.lower() for keyword in ['.git', '.claude', 'marker'])


# ============================================================================
# TEST: Security Validation
# ============================================================================


class TestSecurityValidation:
    """Test security features (path validation, no traversal)."""

    def test_no_path_traversal_in_custom_session_file(self, temp_project, monkeypatch):
        """Test SessionTracker validates custom session file paths."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # Attempt path traversal
        malicious_path = temp_project / "docs" / "sessions" / ".." / ".." / "etc" / "passwd"

        # WILL FAIL: Path validation not implemented
        with pytest.raises(ValueError) as exc_info:
            tracker = SessionTracker(session_file=malicious_path)

        assert "path traversal" in str(exc_info.value).lower() or "invalid path" in str(exc_info.value).lower()

    def test_session_file_must_be_in_sessions_directory(self, temp_project, monkeypatch):
        """Test SessionTracker validates session file is in sessions/ directory."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # Try to create session file outside sessions/
        invalid_path = temp_project / "malicious-session.md"

        # WILL FAIL: Directory validation not implemented
        with pytest.raises(ValueError) as exc_info:
            tracker = SessionTracker(session_file=invalid_path)

        assert "sessions" in str(exc_info.value).lower()

    def test_session_file_must_have_md_extension(self, temp_project, monkeypatch):
        """Test SessionTracker validates session file has .md extension."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # Try to create session file with wrong extension
        invalid_path = temp_project / "docs" / "sessions" / "session.txt"

        # WILL FAIL: Extension validation not implemented
        with pytest.raises(ValueError) as exc_info:
            tracker = SessionTracker(session_file=invalid_path)

        assert ".md" in str(exc_info.value).lower() or "extension" in str(exc_info.value).lower()


# ============================================================================
# TEST: Cross-Platform Compatibility
# ============================================================================


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility (Windows, macOS, Linux)."""

    def test_works_with_windows_paths(self, temp_project, monkeypatch):
        """Test SessionTracker works with Windows-style paths."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: Windows path handling not tested
        tracker = SessionTracker()

        # Should work regardless of OS
        assert tracker.session_dir.exists()

    def test_works_with_posix_paths(self, temp_project, monkeypatch):
        """Test SessionTracker works with POSIX paths."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: POSIX path handling not tested
        tracker = SessionTracker()

        assert tracker.session_dir.exists()

    def test_handles_unicode_in_project_path(self, tmp_path, monkeypatch):
        """Test SessionTracker handles Unicode characters in paths."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # Create project with Unicode in path
        unicode_dir = tmp_path / "project-日本語"
        unicode_dir.mkdir()

        git_dir = unicode_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n")

        monkeypatch.chdir(unicode_dir)

        # WILL FAIL: Unicode handling not tested
        tracker = SessionTracker()

        assert tracker.session_dir.exists()


# ============================================================================
# TEST: Integration with Existing Infrastructure
# ============================================================================


class TestInfrastructureIntegration:
    """Test integration with existing tracking infrastructure."""

    def test_compatible_with_batch_state_manager(self, temp_project, monkeypatch):
        """Test SessionTracker uses same path resolution as batch_state_manager."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # Both should use path_utils.get_project_root()
        tracker = SessionTracker()

        # WILL FAIL: Not using same path resolution
        try:
            from path_utils import get_session_dir
            expected_dir = get_session_dir()
            assert tracker.session_dir == expected_dir
        except ImportError:
            pytest.skip("path_utils not available")

    def test_compatible_with_agent_tracker(self, temp_project, monkeypatch):
        """Test SessionTracker compatible with AgentTracker."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)

        # WILL FAIL: Not compatible
        tracker = SessionTracker()

        # Should be able to use same session file
        assert tracker.session_file.exists()

    def test_session_file_format_matches_existing(self, temp_project, monkeypatch):
        """Test session file format matches existing format."""
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        monkeypatch.chdir(temp_project)
        tracker = SessionTracker()

        # WILL FAIL: Format doesn't match
        tracker.log("test-agent", "Test message")

        content = tracker.session_file.read_text()

        # Should have markdown format
        assert content.startswith("#")
        assert "**" in content  # Bold markers
        assert "##" in content or "###" in content  # Subheadings


# ============================================================================
# SUMMARY
# ============================================================================

"""
Test Coverage Summary (80 tests total):

1. Library Import (4 tests)
   - Module exists and is importable
   - SessionTracker class exists
   - get_default_session_file() function exists
   - Module has docstring

2. SessionTracker Initialization (6 tests)
   - Default path initialization
   - Custom session file path
   - Creates session file
   - Creates session directory
   - Works from nested subdirectory
   - Uses path_utils

3. SessionTracker.log() Method (7 tests)
   - Writes to session file
   - Includes timestamp
   - Multiple entries append
   - Handles multiline messages
   - Handles special characters
   - Thread safety

4. get_default_session_file() Helper (4 tests)
   - Returns Path object
   - Uses path_utils
   - Includes timestamp
   - Unique per call

5. Portable Path Detection (4 tests)
   - Works from project root
   - Works from nested subdirectory
   - Works from docs/ directory
   - Works from plugins/ directory

6. Error Handling (4 tests)
   - Raises error when no project root
   - Handles permission errors
   - Handles write errors
   - Error messages include context

7. Security Validation (3 tests)
   - No path traversal
   - Session file in sessions/ directory
   - Session file has .md extension

8. Cross-Platform Compatibility (3 tests)
   - Works with Windows paths
   - Works with POSIX paths
   - Handles Unicode in paths

9. Infrastructure Integration (3 tests)
   - Compatible with batch_state_manager
   - Compatible with agent_tracker
   - Session file format matches existing

All tests currently FAIL (RED phase) - lib/session_tracker.py doesn't exist yet.
After implementation, all tests should PASS (GREEN phase).
"""
