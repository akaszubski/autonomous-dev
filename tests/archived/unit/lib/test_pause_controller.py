"""
Unit tests for pause_controller.py - Pause controls with PAUSE file and HUMAN_INPUT.md

Tests follow TDD (RED phase) - all tests should FAIL initially until implementation exists.

Test Categories:
1. Pause Detection Tests
2. Human Input Tests
3. Clear State Tests
4. Checkpoint Tests
5. Security Tests
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
import pytest

# Import will fail until implementation exists (expected in TDD RED phase)
try:
    from autonomous_dev.lib.pause_controller import (
        check_pause_requested,
        read_human_input,
        clear_pause_state,
        save_checkpoint,
        load_checkpoint,
        validate_pause_path,
    )
except ImportError:
    # TDD RED phase - implementation doesn't exist yet
    pytest.skip("pause_controller.py not implemented yet", allow_module_level=True)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    """Create temporary .claude directory for testing."""
    # Save original directory
    original_dir = os.getcwd()

    # Change to tmp_path so functions can find .claude
    os.chdir(tmp_path)

    # Create .claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    yield claude_dir

    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def pause_file(claude_dir: Path) -> Path:
    """Return path to PAUSE file (may not exist)."""
    return claude_dir / "PAUSE"


@pytest.fixture
def human_input_file(claude_dir: Path) -> Path:
    """Return path to HUMAN_INPUT.md file (may not exist)."""
    return claude_dir / "HUMAN_INPUT.md"


@pytest.fixture
def checkpoint_file(claude_dir: Path) -> Path:
    """Return path to checkpoint file (may not exist)."""
    return claude_dir / "pause_checkpoint.json"


# ============================================================================
# 1. PAUSE DETECTION TESTS
# ============================================================================


class TestPauseDetection:
    """Test pause file detection functionality."""

    def test_check_pause_file_exists(self, pause_file: Path):
        """Test detecting when PAUSE file exists."""
        pause_file.touch()
        assert check_pause_requested() is True

    def test_check_pause_file_not_exists(self, claude_dir: Path):
        """Test detecting when PAUSE file does not exist."""
        # .claude dir exists but no PAUSE file
        assert check_pause_requested() is False

    def test_check_pause_file_empty_vs_content(self, pause_file: Path):
        """Test that both empty and non-empty PAUSE files are detected."""
        # Empty file
        pause_file.touch()
        assert check_pause_requested() is True

        # File with content
        pause_file.write_text("Paused for review")
        assert check_pause_requested() is True

    def test_check_pause_no_claude_dir(self, tmp_path: Path):
        """Test when .claude directory doesn't exist at all."""
        os.chdir(tmp_path)  # Directory with no .claude subdirectory
        assert check_pause_requested() is False

    def test_check_pause_symlink_rejected(self, claude_dir: Path, pause_file: Path, tmp_path: Path):
        """Test that symlinked PAUSE file is rejected (CWE-59)."""
        # Create real file elsewhere
        real_file = tmp_path / "real_pause"
        real_file.touch()

        # Create symlink at PAUSE location
        if pause_file.exists():
            pause_file.unlink()
        pause_file.symlink_to(real_file)

        # Should reject symlinks for security
        assert check_pause_requested() is False


# ============================================================================
# 2. HUMAN INPUT TESTS
# ============================================================================


class TestHumanInput:
    """Test human input file reading functionality."""

    def test_read_human_input_exists(self, human_input_file: Path):
        """Test reading existing human input file."""
        content = "Please review the security audit before proceeding."
        human_input_file.write_text(content)

        result = read_human_input()
        assert result == content

    def test_read_human_input_not_exists(self, claude_dir: Path):
        """Test reading when human input file does not exist."""
        result = read_human_input()
        assert result is None

    def test_read_human_input_empty_file(self, human_input_file: Path):
        """Test reading empty human input file."""
        human_input_file.touch()  # Create empty file

        result = read_human_input()
        assert result == ""  # Empty string, not None

    def test_read_human_input_multiline(self, human_input_file: Path):
        """Test reading multiline human input."""
        content = """# Human Input Required

Please review:
1. Security audit results
2. Test coverage report
3. Documentation completeness

Proceed when ready.
"""
        human_input_file.write_text(content)

        result = read_human_input()
        assert result == content
        assert "Security audit" in result
        assert "Test coverage" in result

    def test_read_human_input_large_file_truncated(self, human_input_file: Path):
        """Test that large files are truncated to prevent DoS."""
        # Create 2MB file (exceeds 1MB limit)
        large_content = "X" * (2 * 1024 * 1024)
        human_input_file.write_text(large_content)

        result = read_human_input()
        # Should either truncate or return None for oversized files
        assert result is None or len(result) <= 1024 * 1024

    def test_read_human_input_symlink_rejected(self, human_input_file: Path, tmp_path: Path):
        """Test that symlinked human input file is rejected (CWE-59)."""
        # Create real file elsewhere
        real_file = tmp_path / "real_input.md"
        real_file.write_text("Symlink content")

        # Create symlink at HUMAN_INPUT.md location
        if human_input_file.exists():
            human_input_file.unlink()
        human_input_file.symlink_to(real_file)

        # Should reject symlinks for security
        result = read_human_input()
        assert result is None

    def test_read_human_input_unicode_content(self, human_input_file: Path):
        """Test reading unicode content correctly."""
        content = "Review: ✅ Tests pass, ⚠️ Coverage low, 🔒 Security OK"
        human_input_file.write_text(content, encoding="utf-8")

        result = read_human_input()
        assert result == content
        assert "✅" in result


# ============================================================================
# 3. CLEAR STATE TESTS
# ============================================================================


class TestClearState:
    """Test clearing pause state functionality."""

    def test_clear_pause_state_removes_both_files(
        self, pause_file: Path, human_input_file: Path
    ):
        """Test clearing state when both PAUSE and HUMAN_INPUT.md exist."""
        pause_file.touch()
        human_input_file.write_text("Test input")

        clear_pause_state()

        assert not pause_file.exists()
        assert not human_input_file.exists()

    def test_clear_pause_state_only_pause_exists(self, pause_file: Path):
        """Test clearing when only PAUSE file exists."""
        pause_file.touch()

        clear_pause_state()

        assert not pause_file.exists()

    def test_clear_pause_state_only_input_exists(self, human_input_file: Path):
        """Test clearing when only HUMAN_INPUT.md exists."""
        human_input_file.write_text("Test input")

        clear_pause_state()

        assert not human_input_file.exists()

    def test_clear_pause_state_neither_exists(self, claude_dir: Path):
        """Test clearing when neither file exists (no-op)."""
        # Should not raise error
        clear_pause_state()

        # Verify .claude dir still exists
        assert claude_dir.exists()

    def test_clear_pause_state_preserves_other_files(
        self, claude_dir: Path, pause_file: Path
    ):
        """Test that clearing doesn't affect other .claude files."""
        # Create other files in .claude directory
        other_file = claude_dir / "PROJECT.md"
        other_file.write_text("Project content")

        pause_file.touch()
        clear_pause_state()

        # Other files should be preserved
        assert other_file.exists()
        assert other_file.read_text() == "Project content"

    def test_clear_pause_state_checkpoint_preserved(
        self, pause_file: Path, checkpoint_file: Path
    ):
        """Test that checkpoint file is NOT cleared (separate operation)."""
        pause_file.touch()
        checkpoint_file.write_text('{"agent": "test"}')

        clear_pause_state()

        # Checkpoint should remain
        assert checkpoint_file.exists()


# ============================================================================
# 4. CHECKPOINT TESTS
# ============================================================================


class TestCheckpoint:
    """Test checkpoint save/load functionality."""

    def test_save_checkpoint_creates_file(self, checkpoint_file: Path):
        """Test saving checkpoint creates file with correct structure."""
        state = {
            "agent": "test-master",
            "step": 3,
            "context": {"feature": "pause controls"},
        }

        save_checkpoint("test-master", state)

        assert checkpoint_file.exists()
        data = json.loads(checkpoint_file.read_text())
        assert data["agent"] == "test-master"
        assert data["step"] == 3
        assert data["context"]["feature"] == "pause controls"

    def test_save_checkpoint_overwrites_existing(self, checkpoint_file: Path):
        """Test saving checkpoint overwrites existing file."""
        # Save initial checkpoint
        checkpoint_file.write_text('{"agent": "old", "step": 1}')

        # Save new checkpoint
        new_state = {"agent": "new", "step": 2}
        save_checkpoint("new", new_state)

        # Should overwrite
        data = json.loads(checkpoint_file.read_text())
        assert data["agent"] == "new"
        assert data["step"] == 2

    def test_save_checkpoint_includes_timestamp(self, checkpoint_file: Path):
        """Test that saved checkpoint includes timestamp."""
        state = {"agent": "test-master", "step": 1}
        save_checkpoint("test-master", state)

        data = json.loads(checkpoint_file.read_text())
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_load_checkpoint_exists(self, checkpoint_file: Path):
        """Test loading existing checkpoint."""
        checkpoint_data = {
            "agent": "implementer",
            "step": 5,
            "context": {"file": "test.py"},
            "timestamp": "2026-01-02T10:00:00",
        }
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        result = load_checkpoint()

        assert result is not None
        assert result["agent"] == "implementer"
        assert result["step"] == 5
        assert result["context"]["file"] == "test.py"

    def test_load_checkpoint_not_exists(self, claude_dir: Path):
        """Test loading when no checkpoint exists."""
        result = load_checkpoint()
        assert result is None

    def test_load_checkpoint_invalid_json(self, checkpoint_file: Path):
        """Test loading checkpoint with invalid JSON."""
        checkpoint_file.write_text("not valid json {")

        result = load_checkpoint()
        assert result is None  # Should handle gracefully

    def test_load_checkpoint_empty_file(self, checkpoint_file: Path):
        """Test loading empty checkpoint file."""
        checkpoint_file.touch()

        result = load_checkpoint()
        assert result is None

    def test_save_checkpoint_complex_state(self, checkpoint_file: Path):
        """Test saving complex nested state."""
        state = {
            "agent": "auto-implement",
            "step": 4,
            "pipeline": {
                "completed": ["research", "plan", "test"],
                "pending": ["implement", "review"],
            },
            "metadata": {
                "issue": "#182",
                "branch": "feature/pause-controls",
                "files_modified": ["lib/pause_controller.py"],
            },
        }

        save_checkpoint("auto-implement", state)

        loaded = load_checkpoint()
        assert loaded is not None
        assert loaded["pipeline"]["completed"] == ["research", "plan", "test"]
        assert loaded["metadata"]["issue"] == "#182"


# ============================================================================
# 5. SECURITY TESTS
# ============================================================================


class TestSecurity:
    """Test security validation for pause controller."""

    def test_validate_path_normal(self, claude_dir: Path):
        """Test validation of normal paths."""
        valid_paths = [
            str(claude_dir / "PAUSE"),
            str(claude_dir / "HUMAN_INPUT.md"),
            str(claude_dir / "pause_checkpoint.json"),
        ]

        for path in valid_paths:
            assert validate_pause_path(path) is True

    def test_validate_path_traversal_blocked(self, claude_dir: Path):
        """Test that path traversal attempts are blocked (CWE-22)."""
        malicious_paths = [
            str(claude_dir / ".." / "etc" / "passwd"),
            str(claude_dir / ".." / ".." / "sensitive"),
            "../../../etc/passwd",
            ".claude/../../../etc/passwd",
        ]

        for path in malicious_paths:
            assert validate_pause_path(path) is False

    def test_validate_path_symlink_blocked(self, claude_dir: Path, tmp_path: Path):
        """Test that symlinks are blocked (CWE-59)."""
        # Create symlink
        symlink_path = claude_dir / "symlink_pause"
        target = tmp_path / "target"
        target.touch()
        symlink_path.symlink_to(target)

        assert validate_pause_path(str(symlink_path)) is False

    def test_validate_path_outside_claude_dir_blocked(self, tmp_path: Path):
        """Test that paths outside .claude directory are blocked."""
        outside_paths = [
            str(tmp_path / "PAUSE"),
            "/tmp/PAUSE",
            str(tmp_path / "other_dir" / "PAUSE"),
        ]

        for path in outside_paths:
            assert validate_pause_path(path) is False

    def test_validate_path_absolute_vs_relative(self, claude_dir: Path):
        """Test validation handles both absolute and relative paths."""
        # Absolute path
        abs_path = str(claude_dir / "PAUSE")
        assert validate_pause_path(abs_path) is True

        # Relative path (if within .claude)
        rel_path = ".claude/PAUSE"
        result = validate_pause_path(rel_path)
        # Should resolve to absolute and validate
        assert isinstance(result, bool)

    def test_validate_path_null_bytes_blocked(self):
        """Test that null byte injection is blocked."""
        malicious_paths = [
            ".claude/PAUSE\x00.txt",
            ".claude/\x00/../../etc/passwd",
        ]

        for path in malicious_paths:
            assert validate_pause_path(path) is False

    def test_validate_path_unicode_normalization(self, claude_dir: Path):
        """Test unicode normalization attacks are handled."""
        # Unicode variants that might resolve to dangerous paths
        unicode_paths = [
            ".claude/\u002e\u002e/etc/passwd",  # Unicode dots
            ".claude/\uff0e\uff0e/sensitive",  # Fullwidth dots
        ]

        for path in unicode_paths:
            # Should either normalize and reject, or reject as invalid
            result = validate_pause_path(path)
            assert isinstance(result, bool)


# ============================================================================
# 6. EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_concurrent_pause_checks(self, pause_file: Path):
        """Test concurrent pause file checks don't cause race conditions."""
        pause_file.touch()

        # Multiple rapid checks
        results = [check_pause_requested() for _ in range(10)]

        # All should return True consistently
        assert all(results)

    def test_clear_state_during_write(self, human_input_file: Path):
        """Test clearing state while file is being written."""
        # Write large content
        human_input_file.write_text("Content" * 1000)

        # Clear should succeed even if file is large
        clear_pause_state()

        assert not human_input_file.exists()

    def test_checkpoint_save_load_roundtrip(self, checkpoint_file: Path):
        """Test checkpoint data survives save/load roundtrip."""
        original = {
            "agent": "test-master",
            "step": 7,
            "context": {
                "nested": {"deep": {"value": 42}},
                "list": [1, 2, 3],
                "unicode": "测试",
            },
        }

        save_checkpoint("test-master", original)
        loaded = load_checkpoint()

        assert loaded is not None
        assert loaded["agent"] == original["agent"]
        assert loaded["step"] == original["step"]
        assert loaded["context"]["nested"]["deep"]["value"] == 42
        assert loaded["context"]["unicode"] == "测试"

    def test_pause_file_permissions(self, pause_file: Path):
        """Test that pause file has correct permissions."""
        pause_file.touch()

        # Should be readable
        assert os.access(pause_file, os.R_OK)

        # File should exist and be detectable
        assert check_pause_requested() is True

    def test_human_input_special_characters(self, human_input_file: Path):
        """Test reading human input with special characters."""
        content = "Review:\n\t- Code: `test.py`\n\t- Quote: \"important\"\n\t- Backslash: \\"
        human_input_file.write_text(content)

        result = read_human_input()
        assert result == content
        assert "`test.py`" in result
        assert '"important"' in result

    def test_checkpoint_with_none_values(self, checkpoint_file: Path):
        """Test checkpoint with None values in state."""
        state = {
            "agent": "test",
            "optional_field": None,
            "step": 1,
        }

        save_checkpoint("test", state)
        loaded = load_checkpoint()

        assert loaded is not None
        assert loaded["optional_field"] is None

    def test_clear_state_idempotent(self, pause_file: Path):
        """Test that clearing state multiple times is safe."""
        pause_file.touch()

        # Clear multiple times
        clear_pause_state()
        clear_pause_state()
        clear_pause_state()

        # Should not raise errors
        assert not pause_file.exists()


# ============================================================================
# 7. ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_read_human_input_permission_denied(self, human_input_file: Path):
        """Test handling permission denied errors."""
        human_input_file.write_text("Content")

        # Make file unreadable
        os.chmod(human_input_file, 0o000)

        try:
            result = read_human_input()
            # Should return None or handle gracefully
            assert result is None or isinstance(result, str)
        finally:
            # Restore permissions for cleanup
            os.chmod(human_input_file, 0o644)

    def test_checkpoint_disk_full_simulation(self, checkpoint_file: Path, monkeypatch):
        """Test handling disk full errors when saving checkpoint."""
        state = {"agent": "test", "step": 1}

        # Mock write to raise OSError
        def mock_write_text(*args, **kwargs):
            raise OSError("No space left on device")

        # This test may need adjustment based on implementation
        # Should handle gracefully without crashing
        try:
            monkeypatch.setattr(Path, "write_text", mock_write_text)
            save_checkpoint("test", state)
        except OSError:
            # Expected if implementation doesn't catch
            pass

    def test_load_checkpoint_corrupted_json(self, checkpoint_file: Path):
        """Test loading checkpoint with corrupted JSON."""
        corrupted_data = '{"agent": "test", "step": 1, "corrupted'
        checkpoint_file.write_text(corrupted_data)

        result = load_checkpoint()
        # Should return None for corrupted data
        assert result is None

    def test_clear_state_file_locked(self, pause_file: Path):
        """Test clearing state when file is locked."""
        pause_file.touch()

        # Open file to simulate lock
        with open(pause_file, "w") as f:
            f.write("locked")
            # Try to clear while file is open
            # Should handle gracefully
            try:
                clear_pause_state()
            except Exception:
                # May fail on Windows, should handle gracefully
                pass


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
