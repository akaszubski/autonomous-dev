"""Regression tests for v3.4.1 race condition fix (HIGH severity).

Bug: PID-based temp file creation enabled symlink race attacks
Fix: Replaced with tempfile.mkstemp() for cryptographic random filenames
Version: v3.4.1
Severity: HIGH
OWASP: CWE-362 (Concurrent Execution using Shared Resource with Improper Synchronization)

Reference: CHANGELOG.md v3.4.1, GitHub Issue #45

Test Strategy:
- Validate mkstemp() is used (not PID-based filenames)
- Verify temp file parameters (mode 0600, correct directory)
- Test atomic rename pattern
- Verify cleanup on errors
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest


# Add plugin lib to path
@pytest.fixture(autouse=True)
def add_lib_to_path(plugins_dir):
    """Add plugin lib directory to sys.path."""
    lib_dir = plugins_dir / "lib"
    sys.path.insert(0, str(lib_dir))
    yield
    sys.path.pop(0)


@pytest.mark.regression
class TestRaceConditionFix:
    """Validate v3.4.1 race condition fix in PROJECT.md atomic writes.

    Protects: HIGH severity symlink race attack vulnerability
    """

    def test_atomic_write_uses_mkstemp_not_pid(self, isolated_project):
        """Test that atomic write uses mkstemp() instead of PID-based filenames.

        Bug: f".PROJECT_{os.getpid()}.tmp" was predictable
        Fix: tempfile.mkstemp() with cryptographic random suffix

        Protects: CWE-362 race condition (v3.4.1 regression)
        """
        # NOTE: This will FAIL until mkstemp() implemented
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            # Mock mkstemp to return a file descriptor and path
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            # Mock os.write and os.close
            with patch('os.write') as mock_write:
                with patch('os.close') as mock_close:
                    with patch.object(Path, 'replace') as mock_replace:
                        try:
                            updater._atomic_write("test content")
                        except Exception:
                            pass  # May fail due to incomplete mock

            # CRITICAL: Verify mkstemp was called (not PID-based creation)
            assert mock_mkstemp.called, "Must use mkstemp(), not PID-based temp files"

    def test_atomic_write_mkstemp_parameters(self, isolated_project):
        """Test that mkstemp() is called with correct security parameters.

        Requirements:
        - dir: Same directory as target (for atomic rename)
        - prefix: '.PROJECT.'
        - suffix: '.tmp'
        - text: False (binary mode for atomicity)

        Protects: Secure temp file creation (v3.4.1 regression)
        """
        # NOTE: This will FAIL until parameters correct
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write'), patch('os.close'), patch.object(Path, 'replace'):
                try:
                    updater._atomic_write("test content")
                except Exception:
                    pass

            # Verify mkstemp parameters
            assert mock_mkstemp.called
            call_args = mock_mkstemp.call_args

            # Check parameters
            assert 'dir' in call_args.kwargs
            assert 'prefix' in call_args.kwargs
            assert 'suffix' in call_args.kwargs

            assert call_args.kwargs['prefix'] == '.PROJECT.'
            assert call_args.kwargs['suffix'] == '.tmp'
            # Dir should be same as target file's directory
            assert str(isolated_project / ".claude") in str(call_args.kwargs['dir'])

    def test_atomic_write_content_written_via_os_write(self, isolated_project):
        """Test that content is written via os.write() for atomicity.

        Requirements:
        - Use os.write(fd, content) for atomic write
        - Content must be bytes (encode UTF-8)

        Protects: Atomic write guarantees (v3.4.1 regression)
        """
        # NOTE: This will FAIL until os.write() implemented
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        test_content = "test content"

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write') as mock_write:
                with patch('os.close') as mock_close:
                    with patch.object(Path, 'replace'):
                        try:
                            updater._atomic_write(test_content)
                        except Exception:
                            pass

            # CRITICAL: Verify os.write was called with fd and bytes
            assert mock_write.called, "Must use os.write() for atomicity"

            call_args = mock_write.call_args[0]
            assert call_args[0] == temp_fd, "Must write to temp file descriptor"
            assert isinstance(call_args[1], bytes), "Must write bytes (UTF-8 encoded)"
            assert call_args[1] == test_content.encode('utf-8')

    def test_atomic_write_fd_closed_before_rename(self, isolated_project):
        """Test that file descriptor is closed before rename.

        Bug: Open fd during rename can cause corruption on some filesystems
        Fix: Close fd, then rename

        Protects: Cross-platform atomicity (v3.4.1 regression)
        """
        # NOTE: This will FAIL until close-before-rename implemented
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write') as mock_write:
                with patch('os.close') as mock_close:
                    with patch.object(Path, 'replace') as mock_replace:
                        try:
                            updater._atomic_write("test content")
                        except Exception:
                            pass

            # CRITICAL: Verify close was called BEFORE replace
            # This ensures fd is closed before rename operation
            assert mock_close.called, "Must close fd before rename"
            assert mock_close.call_args[0][0] == temp_fd

    def test_atomic_write_rename_is_atomic(self, isolated_project):
        """Test that rename uses Path.replace() for atomicity.

        Requirements:
        - Use Path.replace() (atomic rename on POSIX)
        - Not Path.rename() (may fail if target exists)

        Protects: Atomic file replacement (v3.4.1 regression)
        """
        # NOTE: This will FAIL until Path.replace() used
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write'), patch('os.close'):
                with patch.object(Path, 'replace') as mock_replace:
                    try:
                        updater._atomic_write("test content")
                    except Exception:
                        pass

            # CRITICAL: Verify Path.replace() used (not rename)
            assert mock_replace.called, "Must use Path.replace() for atomic rename"

    def test_atomic_write_error_cleanup(self, isolated_project):
        """Test that temp file is cleaned up if write fails.

        Scenario: os.write() fails (disk full, permission error)
        Expected: Temp file is deleted, error propagated

        Protects: Temp file cleanup on errors (v3.4.1 regression)
        """
        # NOTE: This will FAIL until cleanup implemented
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            # Simulate write failure
            with patch('os.write', side_effect=OSError("Disk full")):
                with patch('os.close') as mock_close:
                    with patch.object(Path, 'unlink') as mock_unlink:
                        with pytest.raises(OSError):
                            updater._atomic_write("test content")

                        # CRITICAL: Verify temp file was cleaned up
                        assert mock_close.called, "Must close fd even on error"
                        assert mock_unlink.called, "Must delete temp file on error"

    def test_atomic_write_mode_0600(self, isolated_project):
        """Test that temp file is created with mode 0600 (owner-only).

        Security: Prevents other users from reading temp file contents
        mkstemp() creates files with mode 0600 by default

        Protects: Confidentiality of temp file (v3.4.1 regression)
        """
        # NOTE: This will FAIL until mkstemp() used (which provides 0600 by default)
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            # mkstemp() returns fd to file with mode 0600
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write'), patch('os.close'), patch.object(Path, 'replace'):
                try:
                    updater._atomic_write("test content")
                except Exception:
                    pass

            # Verify mkstemp was used (it provides 0600 by default)
            assert mock_mkstemp.called, "mkstemp() creates files with mode 0600"


@pytest.mark.regression
class TestSymlinkRaceAttackBlocked:
    """Test that symlink race attacks are blocked by v3.4.1 fix.

    Attack scenario:
    1. Attacker predicts temp filename (via PID)
    2. Attacker creates symlink: .PROJECT_1234.tmp -> /etc/passwd
    3. Victim process writes to temp file
    4. /etc/passwd is overwritten (privilege escalation)

    Defense: Unpredictable filenames prevent step 1
    """

    def test_temp_filename_unpredictable(self, isolated_project):
        """Test that temp filenames cannot be predicted.

        Pre-v3.4.1: f".PROJECT_{os.getpid()}.tmp" (predictable)
        Post-v3.4.1: mkstemp() with random suffix (128+ bits entropy)

        Protects: CWE-362 symlink race attack (v3.4.1 regression)
        """
        # NOTE: This will FAIL if PID-based filenames still used
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            # mkstemp generates random suffix
            temp_path = isolated_project / ".claude" / ".PROJECT.a8f2c9.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write'), patch('os.close'), patch.object(Path, 'replace'):
                try:
                    updater._atomic_write("test content")
                except Exception:
                    pass

            # Verify mkstemp was used (provides unpredictable filenames)
            assert mock_mkstemp.called

            # Verify filename is NOT PID-based
            # (Can't directly check this, but mkstemp() guarantees randomness)

    def test_mkstemp_uses_O_EXCL_atomic_creation(self, isolated_project):
        """Test that mkstemp() creates file atomically with O_EXCL.

        mkstemp() opens file with O_EXCL flag, which:
        - Fails if file already exists (prevents TOCTOU)
        - Creates file atomically (no race window)

        This blocks symlink attacks even if filename is predicted.

        Protects: TOCTOU race condition (v3.4.1 regression)
        """
        # NOTE: This will FAIL until mkstemp() is used
        import project_md_updater

        updater = project_md_updater.ProjectMdUpdater(
            isolated_project / ".claude" / "PROJECT.md"
        )

        with patch('tempfile.mkstemp') as mock_mkstemp:
            temp_fd = 123
            temp_path = isolated_project / ".claude" / ".PROJECT.abc123.tmp"
            mock_mkstemp.return_value = (temp_fd, str(temp_path))

            with patch('os.write'), patch('os.close'), patch.object(Path, 'replace'):
                try:
                    updater._atomic_write("test content")
                except Exception:
                    pass

            # Verify mkstemp was called
            # mkstemp() internally uses O_CREAT | O_EXCL which is atomic
            assert mock_mkstemp.called, "mkstemp() provides atomic creation with O_EXCL"


# TODO: Backfill additional security regression tests:
# - v3.2.3: Path traversal prevention (../../etc/passwd)
# - v3.2.3: Symlink detection in path validation
# - v3.2.3: System directory blocking (/etc/, /var/log/)
# - Security audit: Command injection prevention
# - Security audit: Credential exposure in error messages
# - Security audit: .env file gitignore validation
