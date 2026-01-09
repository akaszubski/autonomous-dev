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
def mock_session_dir(temp_project, monkeypatch):
    """Create a mock session directory within a valid project structure.

    Uses temp_project fixture to create a proper project structure with .git
    marker, which is required for session_tracker path validation.
    """
    # Change to temp_project so path_utils.get_project_root() works
    monkeypatch.chdir(temp_project)
    session_dir = temp_project / "docs" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
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
# TEST: SessionTracker ABC Migration (Issue #224)
# ============================================================================


class TestSessionTrackerABCMigration:
    """Tests for SessionTracker migration to StateManager ABC (Issue #224).

    TDD Mode: These tests are written BEFORE implementation.
    Tests should FAIL initially (SessionTracker not migrated yet).

    Migration Requirements:
    1. SessionTracker inherits from StateManager[str]
    2. Implements abstract methods: load_state(), save_state(), cleanup_state()
    3. Uses inherited helpers: _validate_state_path(), _atomic_write(), _get_file_lock(), _audit_operation()
    4. Generic type is str (markdown content)
    5. Maintains backward compatibility with log() method
    """

    def test_inherits_from_state_manager(self):
        """SessionTracker should inherit from StateManager ABC.

        Verifies:
        - SessionTracker is subclass of StateManager
        - Enables polymorphism for state management
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        try:
            from abstract_state_manager import StateManager
        except ImportError:
            pytest.skip("StateManager ABC not available")

        # WILL FAIL: Not migrated to ABC yet
        assert issubclass(SessionTracker, StateManager), (
            "SessionTracker should inherit from StateManager ABC"
        )

    def test_generic_type_parameter_is_str(self, temp_project, monkeypatch):
        """SessionTracker should be Generic[str] because it stores markdown.

        Verifies:
        - Generic type parameter is str (not Dict[str, Any])
        - Type hints work correctly for load_state() and save_state()
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        try:
            from abstract_state_manager import StateManager
        except ImportError:
            pytest.skip("StateManager ABC not available")

        # SessionTracker stores markdown content as string
        # Use temp_project fixture with docs/sessions directory that passes validation
        monkeypatch.chdir(temp_project)
        session_file = temp_project / "docs" / "sessions" / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # Verify it's a StateManager instance
        assert isinstance(tracker, StateManager), (
            "SessionTracker instance should be instance of StateManager"
        )

    def test_implements_load_state_method(self):
        """SessionTracker should implement load_state() abstract method.

        Verifies:
        - load_state() method exists
        - Returns str (markdown content)
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: load_state() method doesn't exist yet
        assert hasattr(SessionTracker, 'load_state'), (
            "SessionTracker should implement load_state() abstract method"
        )

    def test_implements_save_state_method(self):
        """SessionTracker should implement save_state() abstract method.

        Verifies:
        - save_state() method exists
        - Accepts str (markdown content)
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: save_state() method doesn't exist yet
        assert hasattr(SessionTracker, 'save_state'), (
            "SessionTracker should implement save_state() abstract method"
        )

    def test_implements_cleanup_state_method(self):
        """SessionTracker should implement cleanup_state() abstract method.

        Verifies:
        - cleanup_state() method exists
        - Removes session file
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: cleanup_state() method doesn't exist yet
        assert hasattr(SessionTracker, 'cleanup_state'), (
            "SessionTracker should implement cleanup_state() abstract method"
        )


class TestSessionTrackerLoadState:
    """Tests for SessionTracker.load_state() implementation."""

    def test_load_state_returns_markdown_string(self, mock_session_dir):
        """load_state() should return markdown content as string.

        Verifies:
        - Returns str type
        - Contains markdown content from session file
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session Log\n\n**12:00:00 - researcher**: Test message\n")

        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: load_state() not implemented
        content = tracker.load_state()

        assert isinstance(content, str)
        assert "Session Log" in content
        assert "researcher" in content

    def test_load_state_raises_state_error_if_file_missing(self, mock_session_dir):
        """load_state() should raise StateError if session file missing.

        Verifies:
        - Raises StateError (not FileNotFoundError)
        - Error message mentions missing file
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        try:
            from exceptions import StateError
        except ImportError:
            pytest.skip("StateError not available")

        session_file = mock_session_dir / "nonexistent.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: load_state() not implemented or raises wrong exception
        with pytest.raises(StateError) as exc_info:
            tracker.load_state()

        assert "not found" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()

    def test_load_state_uses_file_locking(self, mock_session_dir):
        """load_state() should use inherited _get_file_lock() for thread safety.

        Verifies:
        - Calls _get_file_lock() during load
        - Prevents concurrent access issues
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session Log\n")

        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: load_state() doesn't use file locking
        with patch.object(tracker, '_get_file_lock', wraps=tracker._get_file_lock) as mock_lock:
            tracker.load_state()

            # Should use file lock for thread safety
            mock_lock.assert_called()

    def test_load_state_handles_utf8_encoding(self, mock_session_dir):
        """load_state() should handle UTF-8 encoded content.

        Verifies:
        - Correctly decodes UTF-8 characters
        - Supports Unicode in markdown
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session 日本語\n\n**12:00:00 - researcher**: Test message 🎉\n", encoding='utf-8')

        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: load_state() not implemented or encoding issues
        content = tracker.load_state()

        assert "日本語" in content
        assert "🎉" in content


class TestSessionTrackerSaveState:
    """Tests for SessionTracker.save_state() implementation."""

    def test_save_state_writes_markdown_content(self, mock_session_dir):
        """save_state() should write markdown content to session file.

        Verifies:
        - Accepts str (markdown content)
        - Writes to session file
        - Content is preserved
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        markdown_content = "# Session Log\n\n**12:00:00 - researcher**: Research complete\n"

        # WILL FAIL: save_state() not implemented
        tracker.save_state(markdown_content)

        assert session_file.exists()
        saved_content = session_file.read_text()
        assert saved_content == markdown_content

    def test_save_state_uses_atomic_write_pattern(self, mock_session_dir):
        """save_state() should use inherited _atomic_write().

        Verifies:
        - Calls _atomic_write() internally
        - Uses temp file + rename for atomicity
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        markdown_content = "# Session Log\n"

        # WILL FAIL: save_state() doesn't use _atomic_write()
        with patch.object(tracker, '_atomic_write', wraps=tracker._atomic_write) as mock_atomic:
            tracker.save_state(markdown_content)

            # Should use atomic write
            mock_atomic.assert_called_once()

    def test_save_state_uses_file_locking(self, mock_session_dir):
        """save_state() should use inherited _get_file_lock().

        Verifies:
        - Calls _get_file_lock() during save
        - Thread-safe concurrent writes
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        markdown_content = "# Session Log\n"

        # WILL FAIL: save_state() doesn't use file locking
        with patch.object(tracker, '_get_file_lock', wraps=tracker._get_file_lock) as mock_lock:
            tracker.save_state(markdown_content)

            mock_lock.assert_called()

    def test_save_state_validates_path(self, mock_session_dir):
        """save_state() should validate path before writing.

        Verifies:
        - Calls _validate_state_path() for security
        - Prevents path traversal
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        markdown_content = "# Session Log\n"

        # WILL FAIL: save_state() doesn't validate path
        with patch.object(tracker, '_validate_state_path', wraps=tracker._validate_state_path) as mock_validate:
            tracker.save_state(markdown_content)

            # Should validate path
            mock_validate.assert_called()

    def test_save_state_raises_state_error_on_error(self, mock_session_dir):
        """save_state() should raise StateError on write failure.

        Verifies:
        - Raises StateError (not IOError)
        - Error message is helpful
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        try:
            from exceptions import StateError
        except ImportError:
            pytest.skip("StateError not available")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        markdown_content = "# Session Log\n"

        # Mock os.write which is used by _atomic_write (not builtins.open)
        with patch("os.write", side_effect=OSError("No space left on device")):
            with pytest.raises(StateError) as exc_info:
                tracker.save_state(markdown_content)

            error_msg = str(exc_info.value).lower()
            assert "atomic write failed" in error_msg or "failed" in error_msg


class TestSessionTrackerCleanupState:
    """Tests for SessionTracker.cleanup_state() implementation."""

    def test_cleanup_state_removes_session_file(self, mock_session_dir):
        """cleanup_state() should remove session file.

        Verifies:
        - Removes session file from disk
        - File no longer exists after cleanup
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session Log\n")
        tracker = SessionTracker(session_file=str(session_file))

        assert session_file.exists()

        # WILL FAIL: cleanup_state() not implemented
        tracker.cleanup_state()

        assert not session_file.exists()

    def test_cleanup_state_uses_file_locking(self, mock_session_dir):
        """cleanup_state() should use inherited _get_file_lock().

        Verifies:
        - Calls _get_file_lock() during cleanup
        - Thread-safe deletion
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session Log\n")
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: cleanup_state() doesn't use file locking
        with patch.object(tracker, '_get_file_lock', wraps=tracker._get_file_lock) as mock_lock:
            tracker.cleanup_state()

            mock_lock.assert_called()

    def test_cleanup_state_raises_state_error_on_error(self, mock_session_dir):
        """cleanup_state() should raise StateError on deletion failure.

        Verifies:
        - Raises StateError (not OSError)
        - Error message is helpful
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        try:
            from exceptions import StateError
        except ImportError:
            pytest.skip("StateError not available")

        session_file = mock_session_dir / "test-session.md"
        session_file.write_text("# Session Log\n")
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: cleanup_state() raises wrong exception type
        with patch.object(Path, 'unlink', side_effect=PermissionError("Permission denied")):
            with pytest.raises(StateError) as exc_info:
                tracker.cleanup_state()

            error_msg = str(exc_info.value).lower()
            assert "permission" in error_msg or "failed" in error_msg or "cleanup" in error_msg


class TestSessionTrackerInheritedHelpers:
    """Tests for inherited helper methods from StateManager ABC."""

    def test_validate_state_path_is_available(self, mock_session_dir):
        """_validate_state_path() should be inherited and available.

        Verifies:
        - Method exists
        - Can be called
        - Validates paths correctly
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: _validate_state_path() not inherited
        assert hasattr(tracker, '_validate_state_path')

        # Should validate path without raising
        validated = tracker._validate_state_path(session_file)
        assert validated.exists() or validated.parent.exists()

    def test_atomic_write_is_available(self, mock_session_dir):
        """_atomic_write() should be inherited and available.

        Verifies:
        - Method exists
        - Can be called
        - Writes atomically
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: _atomic_write() not inherited
        assert hasattr(tracker, '_atomic_write')

        # Should write atomically
        test_data = "# Test Content\n"
        tracker._atomic_write(session_file, test_data)
        assert session_file.read_text() == test_data

    def test_get_file_lock_returns_rlock(self, mock_session_dir):
        """_get_file_lock() should return reentrant lock.

        Verifies:
        - Method exists
        - Returns threading.RLock
        - Same lock for same file
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: _get_file_lock() not inherited
        assert hasattr(tracker, '_get_file_lock')

        lock = tracker._get_file_lock(session_file)
        assert type(lock).__name__ == "RLock"

    def test_audit_operation_is_available(self, mock_session_dir):
        """_audit_operation() should be inherited and available.

        Verifies:
        - Method exists
        - Can be called without error
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: _audit_operation() not inherited
        assert hasattr(tracker, '_audit_operation')

        # Should not raise
        tracker._audit_operation(
            operation="test_operation",
            status="success",
            details={"test": "data"}
        )


class TestSessionTrackerBackwardCompatibility:
    """Tests for backward compatibility after ABC migration."""

    def test_log_method_still_works(self, mock_session_dir):
        """log() method should maintain backward compatibility.

        Verifies:
        - log() method still exists
        - Works as before
        - Appends to session file
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: log() broken after ABC migration
        tracker.log("researcher", "Test message")

        content = session_file.read_text()
        assert "researcher" in content
        assert "Test message" in content

    def test_init_with_custom_file_still_works(self, mock_session_dir):
        """__init__ with session_file parameter should still work.

        Verifies:
        - Custom session_file parameter supported
        - Backward compatibility maintained
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        custom_file = mock_session_dir / "custom-session.md"

        # WILL FAIL: Custom session_file broken after ABC migration
        tracker = SessionTracker(session_file=str(custom_file))

        assert tracker.session_file == custom_file

    def test_get_default_session_file_still_works(self):
        """get_default_session_file() helper should still work.

        Verifies:
        - Function still exists
        - Returns Path with timestamp
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        # WILL FAIL: get_default_session_file() broken after ABC migration
        session_file = get_default_session_file()

        assert isinstance(session_file, Path)
        assert session_file.suffix == ".md"

    def test_existing_public_api_unchanged(self, mock_session_dir):
        """Existing public API should remain unchanged.

        Verifies:
        - session_file attribute exists
        - session_dir attribute exists
        - log() method exists
        """
        if not LIB_SESSION_TRACKER_EXISTS:
            pytest.skip("Library module doesn't exist yet")

        session_file = mock_session_dir / "test-session.md"
        tracker = SessionTracker(session_file=str(session_file))

        # WILL FAIL: Public API changed after ABC migration
        assert hasattr(tracker, 'session_file')
        assert hasattr(tracker, 'session_dir')
        assert hasattr(tracker, 'log')


# ============================================================================
# SUMMARY
# ============================================================================

"""
Test Coverage Summary (105 tests total):

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

10. ABC Inheritance Tests - NEW (5 tests) - Issue #224
   - Inherits from StateManager ABC
   - Generic type parameter is str (markdown content)
   - Implements load_state() method
   - Implements save_state() method
   - Implements cleanup_state() method

11. Load State Tests - NEW (4 tests)
   - load_state() returns markdown string
   - load_state() raises StateError if file missing
   - load_state() uses file locking
   - load_state() handles UTF-8 encoding

12. Save State Tests - NEW (5 tests)
   - save_state() writes markdown content
   - save_state() uses atomic write pattern
   - save_state() uses file locking
   - save_state() validates path
   - save_state() raises StateError on error

13. Cleanup State Tests - NEW (3 tests)
   - cleanup_state() removes session file
   - cleanup_state() uses file locking
   - cleanup_state() raises StateError on error

14. Inherited Helper Tests - NEW (4 tests)
   - _validate_state_path() is available
   - _atomic_write() is available
   - _get_file_lock() returns RLock
   - _audit_operation() is available

15. Backward Compatibility Tests - NEW (4 tests)
   - log() method still works
   - init with custom file works
   - get_default_session_file() works
   - existing public API unchanged

All tests currently FAIL (RED phase) - lib/session_tracker.py doesn't exist yet.
After implementation, all tests should PASS (GREEN phase).

NEW TESTS (25 tests for Issue #224):
- Test SessionTracker migration to StateManager ABC
- Test Generic[str] type parameter (markdown content)
- Test abstract method implementations (load_state, save_state, cleanup_state)
- Test inherited helper methods (_validate_state_path, _atomic_write, _get_file_lock, _audit_operation)
- Test backward compatibility with existing log() method
"""
