"""
Unit Tests for batch_resume_helper.py (Issue #277)

Tests the Python helper that loads RALPH checkpoints for SessionStart hook resumption.
This is Phase 1 of the RALPH-Claude auto-compact integration.

Test Organization:
1. Successful Checkpoint Loading (2 tests) - Valid checkpoint loads correctly
2. Error Conditions (4 tests) - Missing, corrupted, permission errors
3. Security Tests (2 tests) - Path traversal, file permissions

TDD Phase: RED (tests written BEFORE implementation)
Expected: All tests should FAIL initially - batch_resume_helper.py doesn't exist yet

Date: 2026-01-28
Issue: #277 (Integrate RALPH checkpoint with Claude auto-compact lifecycle)
Agent: test-master
Status: RED (TDD red phase - no implementation yet)
"""

import json
import os
import stat
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add lib directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "plugins" / "autonomous-dev" / "lib"))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary checkpoint directory."""
    checkpoint_dir = tmp_path / ".ralph-checkpoints"
    checkpoint_dir.mkdir(parents=True)
    return checkpoint_dir


@pytest.fixture
def sample_batch_id():
    """Sample batch ID for testing."""
    return "batch-20260128-123456"


@pytest.fixture
def sample_checkpoint_data(sample_batch_id):
    """Sample valid checkpoint data."""
    return {
        "session_id": f"ralph-{sample_batch_id}",
        "batch_id": sample_batch_id,
        "current_feature_index": 3,
        "completed_features": [0, 1, 2],
        "failed_features": [],
        "skipped_features": [],
        "total_features": 10,
        "features": [
            "Feature 1: Add authentication",
            "Feature 2: Implement API",
            "Feature 3: Add database",
            "Feature 4: Write tests",
            "Feature 5: Update docs",
            "Feature 6: Add error handling",
            "Feature 7: Implement caching",
            "Feature 8: Add monitoring",
            "Feature 9: Performance optimization",
            "Feature 10: Security audit"
        ],
        "context_token_estimate": 45000,
        "auto_clear_count": 1,
        "created_at": "2026-01-28T10:00:00Z",
        "updated_at": "2026-01-28T14:30:00Z",
        "status": "in_progress"
    }


@pytest.fixture
def valid_checkpoint_file(temp_checkpoint_dir, sample_batch_id, sample_checkpoint_data):
    """Create valid checkpoint file with secure permissions."""
    checkpoint_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json"
    checkpoint_file.write_text(json.dumps(sample_checkpoint_data, indent=2))
    checkpoint_file.chmod(0o600)  # Owner read/write only
    return checkpoint_file


@pytest.fixture
def batch_resume_helper_path():
    """Path to batch_resume_helper.py script."""
    return project_root / "plugins" / "autonomous-dev" / "lib" / "batch_resume_helper.py"


# =============================================================================
# SECTION 1: Successful Checkpoint Loading Tests (2 tests)
# =============================================================================

class TestSuccessfulCheckpointLoading:
    """Test valid checkpoint loading returns correct JSON."""

    def test_load_checkpoint_success(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id,
        valid_checkpoint_file,
        sample_checkpoint_data
    ):
        """
        Test load_checkpoint() returns valid JSON for existing checkpoint.

        Validates:
        - Exit code 0 (success)
        - Valid JSON output
        - Correct batch_id, current_index, total_features
        - Features list intact
        """
        # Arrange
        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act - invoke batch_resume_helper.py
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), sample_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 0 (success)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"

        # Parse JSON output
        try:
            checkpoint_output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {result.stdout}\nError: {e}")

        # Validate checkpoint content
        assert checkpoint_output["batch_id"] == sample_batch_id
        assert checkpoint_output["current_feature_index"] == 3
        assert checkpoint_output["total_features"] == 10
        assert len(checkpoint_output["features"]) == 10
        assert checkpoint_output["status"] == "in_progress"
        assert checkpoint_output["completed_features"] == [0, 1, 2]

    def test_load_checkpoint_next_feature_display(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id,
        valid_checkpoint_file
    ):
        """
        Test load_checkpoint() includes next feature for display.

        Validates SessionStart hook can show: "Resume at Feature 4 of 10"
        """
        # Arrange
        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), sample_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert
        assert result.returncode == 0
        checkpoint_output = json.loads(result.stdout)

        # Check next feature info
        current_index = checkpoint_output["current_feature_index"]
        next_feature_num = current_index + 1
        total = checkpoint_output["total_features"]

        # Verify next feature can be displayed
        assert current_index == 3  # Next is feature 4
        assert next_feature_num == 4
        assert total == 10

        # Verify features list has next feature
        next_feature = checkpoint_output["features"][current_index]
        assert "Feature 4" in next_feature


# =============================================================================
# SECTION 2: Error Conditions Tests (4 tests)
# =============================================================================

class TestErrorConditions:
    """Test error handling for various failure scenarios."""

    def test_load_checkpoint_missing(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir
    ):
        """
        Test load_checkpoint() returns exit code 1 for missing checkpoint.

        Validates:
        - Exit code 1 (missing)
        - Stderr contains helpful error message
        - No JSON output on stdout
        """
        # Arrange
        missing_batch_id = "batch-nonexistent"
        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), missing_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 1 (missing)
        assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"

        # Verify error message
        assert "not found" in result.stderr.lower() or "missing" in result.stderr.lower()

        # Verify no JSON on stdout
        assert result.stdout.strip() == "" or result.stdout.strip().startswith("Error:")

    def test_load_checkpoint_corrupted(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id
    ):
        """
        Test load_checkpoint() returns exit code 2 for corrupted JSON.

        Validates:
        - Exit code 2 (corrupted)
        - Stderr contains parse error info
        - Falls back to .bak if available
        """
        # Arrange - create corrupted checkpoint
        checkpoint_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json"
        checkpoint_file.write_text("{invalid json corrupt data")
        checkpoint_file.chmod(0o600)

        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), sample_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 2 (corrupted)
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"

        # Verify error message mentions corruption
        assert "corrupt" in result.stderr.lower() or "parse" in result.stderr.lower() or "invalid json" in result.stderr.lower()

    def test_load_checkpoint_bad_permissions(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id,
        sample_checkpoint_data
    ):
        """
        Test load_checkpoint() returns exit code 3 for insecure permissions.

        Validates:
        - Exit code 3 (permission error)
        - Rejects world-readable files (0o644)
        - Security requirement: only 0o600 accepted
        """
        # Arrange - create checkpoint with insecure permissions
        checkpoint_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json"
        checkpoint_file.write_text(json.dumps(sample_checkpoint_data, indent=2))
        checkpoint_file.chmod(0o644)  # World-readable (INSECURE)

        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), sample_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 3 (permission error)
        assert result.returncode == 3, f"Expected exit code 3, got {result.returncode}"

        # Verify error message mentions permissions
        assert "permission" in result.stderr.lower() or "mode" in result.stderr.lower() or "0o600" in result.stderr

    def test_load_checkpoint_fallback_to_backup(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id,
        sample_checkpoint_data
    ):
        """
        Test load_checkpoint() falls back to .bak when main checkpoint corrupted.

        Validates:
        - Corrupted main checkpoint
        - Valid .bak exists
        - Returns exit code 0 with backup data
        - Warning in stderr about using backup
        """
        # Arrange - corrupt main checkpoint
        checkpoint_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json"
        checkpoint_file.write_text("{invalid json")
        checkpoint_file.chmod(0o600)

        # Create valid backup
        backup_data = sample_checkpoint_data.copy()
        backup_data["current_feature_index"] = 2  # Slightly behind
        backup_data["completed_features"] = [0, 1]

        backup_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json.bak"
        backup_file.write_text(json.dumps(backup_data, indent=2))
        backup_file.chmod(0o600)

        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), sample_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 0 (success via backup)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"

        # Verify loaded from backup
        checkpoint_output = json.loads(result.stdout)
        assert checkpoint_output["current_feature_index"] == 2  # From backup
        assert checkpoint_output["completed_features"] == [0, 1]

        # Verify warning about backup usage
        assert "backup" in result.stderr.lower() or ".bak" in result.stderr.lower()


# =============================================================================
# SECTION 3: Security Tests (2 tests)
# =============================================================================

class TestSecurity:
    """Test security validations (CWE-22, file permissions)."""

    def test_load_checkpoint_path_traversal(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir
    ):
        """
        Test load_checkpoint() rejects path traversal in batch_id (CWE-22).

        Validates:
        - batch_id with ../ rejected
        - Exit code 4 (security error)
        - No file access outside checkpoint dir
        """
        # Arrange - attempt path traversal
        malicious_batch_id = "../../../etc/passwd"
        env = os.environ.copy()
        env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

        # Act
        result = subprocess.run(
            [sys.executable, str(batch_resume_helper_path), malicious_batch_id],
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        # Assert - exit code 4 (security error) or 1 (not found)
        # Implementation may treat this as "not found" or "security violation"
        assert result.returncode in [1, 4], f"Expected exit code 1 or 4, got {result.returncode}"

        # Verify error message
        assert "invalid" in result.stderr.lower() or "not found" in result.stderr.lower() or "security" in result.stderr.lower()

        # Verify no sensitive file accessed
        assert "passwd" not in result.stdout.lower()

    def test_load_checkpoint_validates_0o600_only(
        self,
        batch_resume_helper_path,
        temp_checkpoint_dir,
        sample_batch_id,
        sample_checkpoint_data
    ):
        """
        Test load_checkpoint() accepts only 0o600 file permissions.

        Validates:
        - 0o600: Success (owner read/write only)
        - 0o640: Rejected (group readable)
        - 0o644: Rejected (world readable)
        - 0o400: Rejected (read-only, can't update)
        """
        permission_tests = [
            (0o600, True, "Owner read/write only - VALID"),
            (0o640, False, "Group readable - INVALID"),
            (0o644, False, "World readable - INVALID"),
            (0o400, False, "Read-only - INVALID (can't update checkpoint)"),
        ]

        for perms, should_succeed, description in permission_tests:
            # Arrange
            checkpoint_file = temp_checkpoint_dir / f"ralph-{sample_batch_id}_checkpoint.json"
            checkpoint_file.write_text(json.dumps(sample_checkpoint_data, indent=2))
            checkpoint_file.chmod(perms)

            env = os.environ.copy()
            env["CHECKPOINT_DIR"] = str(temp_checkpoint_dir)

            # Act
            result = subprocess.run(
                [sys.executable, str(batch_resume_helper_path), sample_batch_id],
                capture_output=True,
                text=True,
                env=env,
                timeout=5
            )

            # Assert
            if should_succeed:
                assert result.returncode == 0, f"{description}: Expected success, got {result.returncode}"
            else:
                assert result.returncode == 3, f"{description}: Expected exit code 3 (permission error), got {result.returncode}"

            # Cleanup
            checkpoint_file.unlink()


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (8 unit tests for batch_resume_helper.py):

SECTION 1: Successful Checkpoint Loading (2 tests)
✗ test_load_checkpoint_success
✗ test_load_checkpoint_next_feature_display

SECTION 2: Error Conditions (4 tests)
✗ test_load_checkpoint_missing
✗ test_load_checkpoint_corrupted
✗ test_load_checkpoint_bad_permissions
✗ test_load_checkpoint_fallback_to_backup

SECTION 3: Security (2 tests)
✗ test_load_checkpoint_path_traversal
✗ test_load_checkpoint_validates_0o600_only

Expected Status: ALL TESTS FAILING (RED phase - batch_resume_helper.py doesn't exist yet)
Next Step: Implement batch_resume_helper.py with load_checkpoint() function

Exit Codes:
- 0: Success (valid checkpoint loaded)
- 1: Missing checkpoint file
- 2: Corrupted JSON
- 3: Insecure file permissions
- 4: Security violation (path traversal)

Coverage Target: 90%+ for batch_resume_helper.py
Security Requirements:
- CWE-22: Path traversal validation
- File permissions: 0o600 only
- Backup fallback on corruption
"""
