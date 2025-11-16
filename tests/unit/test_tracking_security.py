#!/usr/bin/env python3
"""
TDD Tests for Tracking Security (Issue #79)

This module tests security enhancements for tracking modules:
- Path traversal prevention (../../etc/passwd)
- Input validation (agent names, messages)
- Symlink attack prevention
- File permission checks

These tests will fail until security validation is implemented.

Security Requirements:
1. Reject paths containing '..' (path traversal)
2. Reject absolute paths outside PROJECT_ROOT
3. Validate all input parameters
4. Prevent symlink-based escapes

Test Coverage Target: 100% of security validation code paths
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.autonomous_dev.lib.session_tracker import SessionTracker
from scripts.agent_tracker import AgentTracker
from plugins.autonomous_dev.lib.batch_state_manager import BatchState, BatchStateManager, create_batch_state, save_batch_state, load_batch_state, DEFAULT_STATE_FILE


class TestSessionTrackerPathTraversal:
    """Test that SessionTracker prevents path traversal attacks."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        return project

    def test_rejects_relative_path_traversal(self, project_root):
        """Test that ../../etc/passwd style paths are rejected.

        SECURITY: Prevent writing files outside project directory.

        Expected:
        - ValueError raised with "path traversal" message
        - No file created outside project
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            # Try to create tracker with traversal in custom session file
            # (This assumes SessionTracker can accept custom session_file)
            malicious_path = "../../etc/passwd"

            with pytest.raises(ValueError, match="[Pp]ath traversal"):
                # This will fail because path traversal detection not implemented yet
                tracker = SessionTracker(session_file=malicious_path)

            # Verify no file created
            assert not (project_root.parent.parent / "etc" / "passwd").exists()

        finally:
            os.chdir(original_cwd)

    def test_rejects_absolute_path_outside_project(self, project_root):
        """Test that absolute paths outside PROJECT_ROOT are rejected.

        SECURITY: Only allow files within project.

        Expected:
        - ValueError for /etc/passwd, /tmp/evil.md, etc.
        """
        malicious_paths = [
            "/etc/passwd",
            "/tmp/malicious.md",
            "/var/log/evil.txt"
        ]

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            for malicious_path in malicious_paths:
                with pytest.raises(ValueError, match="outside project|absolute path"):
                    tracker = SessionTracker(session_file=malicious_path)

        finally:
            os.chdir(original_cwd)

    def test_rejects_double_encoded_traversal(self, project_root):
        """Test that encoded path traversal attempts are rejected.

        SECURITY: Prevent ..%2F..%2Fetc%2Fpasswd attacks.

        Expected:
        - URL-encoded traversal detected and blocked
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            # URL-encoded: ..%2F..%2Fetc%2Fpasswd
            malicious_path = "..%2F..%2Fetc%2Fpasswd"

            with pytest.raises(ValueError):
                tracker = SessionTracker(session_file=malicious_path)

        finally:
            os.chdir(original_cwd)

    def test_normalizes_paths_before_validation(self, project_root):
        """Test that paths are normalized before security checks.

        SECURITY: Prevent attacks using /./, //, or /./.. sequences.

        Expected:
        - Path normalization happens before validation
        - docs/./sessions/ becomes docs/sessions/
        - docs//sessions/ becomes docs/sessions/
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            # These should be normalized to safe paths
            safe_paths = [
                "docs/./sessions/test.md",
                "docs//sessions/test.md",
                "./docs/sessions/test.md"
            ]

            for safe_path in safe_paths:
                # Should not raise error (normalized to docs/sessions/test.md)
                tracker = SessionTracker(session_file=safe_path)
                assert tracker.session_file.is_relative_to(project_root)

        finally:
            os.chdir(original_cwd)


class TestAgentTrackerPathTraversal:
    """Test that AgentTracker prevents path traversal attacks."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        return project

    def test_rejects_path_traversal_in_session_file(self, project_root):
        """Test that AgentTracker rejects path traversal.

        Expected:
        - ValueError raised for ../../etc/passwd
        - No file created outside project
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            malicious_path = "../../etc/passwd"

            with pytest.raises(ValueError, match="[Pp]ath traversal"):
                tracker = AgentTracker(session_file=malicious_path)

        finally:
            os.chdir(original_cwd)

    def test_validates_agent_name_input(self, project_root):
        """Test that agent_name parameter is validated.

        SECURITY: Prevent injection attacks via agent names.

        Expected:
        - Only allow alphanumeric, hyphen, underscore
        - Reject special characters: /../, ;rm -rf, etc.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = AgentTracker()

            # Malicious agent names
            malicious_names = [
                "../../etc/passwd",
                "evil; rm -rf /",
                "agent<script>alert(1)</script>",
                "agent\x00null-byte",
                "../../../root"
            ]

            for malicious_name in malicious_names:
                with pytest.raises(ValueError, match="[Ii]nvalid|[Aa]gent name"):
                    tracker.log_start(malicious_name, "test message")

        finally:
            os.chdir(original_cwd)

    def test_validates_message_length(self, project_root):
        """Test that message parameter has length limits.

        SECURITY: Prevent resource exhaustion via huge messages.

        Expected:
        - Messages limited to reasonable size (e.g., 10KB)
        - ValueError if message too long
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = AgentTracker()

            # Create message exceeding limit (e.g., 10KB)
            huge_message = "A" * 20000  # 20KB message

            with pytest.raises(ValueError, match="[Mm]essage too long|[Ll]ength"):
                tracker.log_start("researcher", huge_message)

        finally:
            os.chdir(original_cwd)


class TestBatchStatePathTraversal:
    """Test that BatchStateManager prevents path traversal attacks."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".claude").mkdir()
        return project

    def test_rejects_path_traversal_in_state_file(self, project_root):
        """Test that state_file parameter rejects path traversal.

        Expected:
        - ValueError for ../../etc/passwd
        - No file created outside project
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            malicious_path = "../../etc/passwd"

            with pytest.raises(ValueError, match="[Pp]ath traversal"):
                manager = BatchStateManager(state_file=malicious_path)

        finally:
            os.chdir(original_cwd)

    def test_rejects_absolute_paths_outside_project(self, project_root):
        """Test that absolute paths are rejected.

        Expected:
        - ValueError for /tmp/state.json, etc.
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            malicious_paths = [
                "/tmp/state.json",
                "/var/lib/batch_state.json",
                "/etc/state.json"
            ]

            for malicious_path in malicious_paths:
                with pytest.raises(ValueError, match="outside project|absolute"):
                    manager = BatchStateManager(state_file=malicious_path)

        finally:
            os.chdir(original_cwd)

    def test_validates_features_file_path(self, project_root):
        """Test that features_file path is validated.

        Expected:
        - Reject path traversal in features_file
        - Only allow files within project
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            manager = BatchStateManager()

            # Create malicious features file path
            malicious_file = "../../etc/passwd"

            with pytest.raises(ValueError, match="[Pp]ath traversal"):
                # Assuming BatchState has features_file parameter
                state = manager.create_batch(
                    features_file=malicious_file,
                    features=["feature1"]
                )

        finally:
            os.chdir(original_cwd)


class TestSymlinkAttackPrevention:
    """Test that symlink-based attacks are prevented."""

    @pytest.fixture
    def project_with_symlinks(self, tmp_path):
        """Create project with symlinks."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        return project

    @pytest.mark.skipif(not hasattr(os, 'symlink'), reason="Symlinks not supported")
    def test_rejects_symlink_outside_project(self, project_with_symlinks):
        """Test that symlinks pointing outside project are rejected.

        SECURITY: Prevent symlink-based path traversal.

        Expected:
        - Resolve symlink to real path
        - Reject if real path outside PROJECT_ROOT
        """
        # Create symlink to outside directory
        outside_target = project_with_symlinks.parent / "outside.txt"
        outside_target.touch()

        symlink_path = project_with_symlinks / "docs" / "sessions" / "link.txt"
        symlink_path.symlink_to(outside_target)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_with_symlinks))

            # Try to use symlink as session file
            with pytest.raises(ValueError, match="outside project|symlink"):
                tracker = SessionTracker(session_file="docs/sessions/link.txt")

        finally:
            os.chdir(original_cwd)

    @pytest.mark.skipif(not hasattr(os, 'symlink'), reason="Symlinks not supported")
    def test_allows_symlink_within_project(self, project_with_symlinks):
        """Test that symlinks are rejected even within project.

        Security Policy: ALL symlinks are rejected (defense-in-depth)
        - Even symlinks within PROJECT_ROOT are not allowed
        - Prevents symlink-based path traversal attacks (CWE-59)
        - More secure than allowing "trusted" symlinks
        """
        # Create symlink to another location within project
        target = project_with_symlinks / "docs" / "sessions" / "real.md"
        target.touch()

        symlink_path = project_with_symlinks / "docs" / "link.md"
        symlink_path.symlink_to(target)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_with_symlinks))

            # Should reject ALL symlinks (security-first policy)
            with pytest.raises(ValueError, match=r"(?i)symlink"):
                tracker = SessionTracker(session_file="docs/link.md")

        finally:
            os.chdir(original_cwd)


class TestInputValidation:
    """Test input validation for all tracking modules."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        (project / ".claude").mkdir()
        return project

    def test_agent_name_validation_format(self, project_root):
        """Test that agent_name must match expected format.

        Expected:
        - Allow: researcher, test-master, doc_master
        - Reject: invalid chars, too long, empty
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = AgentTracker()

            # Valid names
            valid_names = ["researcher", "test-master", "doc_master", "agent_1"]
            for name in valid_names:
                tracker.log_start(name, "test message")

            # Invalid names
            invalid_names = [
                "",  # Empty
                "a" * 300,  # Too long
                "agent/name",  # Invalid char
                "agent name",  # Space
                "agent<script>",  # HTML
            ]

            for name in invalid_names:
                with pytest.raises(ValueError, match="[Ii]nvalid|[Aa]gent name"):
                    tracker.log_start(name, "test message")

        finally:
            os.chdir(original_cwd)

    def test_message_validation_special_characters(self, project_root):
        """Test that messages with special characters are handled safely.

        Expected:
        - Allow normal special chars (punctuation)
        - Sanitize/reject control characters
        - Prevent injection attacks
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = AgentTracker()

            # Valid messages with special chars
            valid_messages = [
                "Research complete: found 3 patterns!",
                "Error: authentication failed (401)",
                "Tests passed: 95/100 ✓",
            ]

            for message in valid_messages:
                tracker.log_start("researcher", message)

            # Invalid messages with control characters
            invalid_messages = [
                "Message with\x00null byte",
                "Message with\x1bESC sequence",
            ]

            for message in invalid_messages:
                with pytest.raises(ValueError, match="[Ii]nvalid|[Cc]ontrol"):
                    tracker.log_start("researcher", message)

        finally:
            os.chdir(original_cwd)

    def test_github_issue_validation(self, project_root):
        """Test that GitHub issue numbers are validated.

        Expected:
        - Allow: positive integers 1-999999
        - Reject: negative, zero, too large, non-numeric
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = AgentTracker()

            # Valid issue numbers
            valid_issues = [1, 42, 999, 123456]
            for issue in valid_issues:
                tracker.log_complete("researcher", "test", github_issue=issue)

            # Invalid issue numbers
            invalid_issues = [0, -1, 1000000, "not-a-number"]

            for issue in invalid_issues:
                with pytest.raises(ValueError, match="[Ii]nvalid|[Ii]ssue"):
                    tracker.log_complete("researcher", "test", github_issue=issue)

        finally:
            os.chdir(original_cwd)


class TestFilePermissions:
    """Test that file permissions are validated."""

    @pytest.fixture
    def project_root(self, tmp_path):
        """Create project structure."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "docs" / "sessions").mkdir(parents=True)
        return project

    @pytest.mark.skipif(os.name == 'nt', reason="POSIX permissions not on Windows")
    def test_rejects_world_writable_session_directory(self, project_root):
        """Test that world-writable directories are rejected.

        SECURITY: Prevent other users from tampering with session files.

        Expected:
        - Warning or error if docs/sessions/ is world-writable (777)
        """
        session_dir = project_root / "docs" / "sessions"
        session_dir.chmod(0o777)  # World-writable

        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            # Should warn or error about insecure permissions
            with pytest.warns(UserWarning, match="[Pp]ermissions|[Ww]orld-writable"):
                tracker = SessionTracker()

        finally:
            os.chdir(original_cwd)

    @pytest.mark.skipif(os.name == 'nt', reason="POSIX permissions not on Windows")
    def test_sets_restrictive_permissions_on_new_files(self, project_root):
        """Test that new session files have restrictive permissions.

        SECURITY: Session files should only be readable by owner.

        Expected:
        - New files created with mode 0o600 (owner read/write only)
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_root))

            tracker = SessionTracker()
            tracker.log("researcher", "test message")

            # Check file permissions
            file_mode = tracker.session_file.stat().st_mode
            # Should be owner read/write only (0o600)
            assert file_mode & 0o077 == 0, "File should not be readable by group/others"

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
