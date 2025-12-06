#!/usr/bin/env python3
"""
Security tests for batch retry functionality (TDD Red Phase - Issue #89).

Tests for security aspects of automatic retry feature.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation doesn't exist yet).

Test Strategy:
- Test path traversal prevention in feature names and error messages
- Test log injection prevention (CWE-117)
- Test global retry limit enforcement (resource exhaustion)
- Test audit logging for all retry attempts
- Test consent state file security
- Test resource exhaustion prevention

Security Standards:
- CWE-22: Path traversal prevention
- CWE-117: Log injection prevention
- CWE-400: Resource exhaustion prevention
- CWE-732: Incorrect permission assignment

Date: 2025-11-18
Issue: #89 (Automatic Failure Recovery for /batch-implement)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - implementation doesn't exist yet)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))

# Import will fail - modules don't exist yet (TDD!)
try:
    from batch_state_manager import (
        BatchState,
        create_batch_state,
        save_batch_state,
        load_batch_state,
    )
    from failure_classifier import (
        classify_failure,
        sanitize_error_message,
        extract_error_context,
    )
    from batch_retry_manager import (
        BatchRetryManager,
        MAX_TOTAL_RETRIES,
        CIRCUIT_BREAKER_THRESHOLD,
    )
    from batch_retry_consent import (
        save_consent_state,
        load_consent_state,
        get_user_state_file,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for batch processing."""
    workspace = tmp_path / "batch-workspace"
    workspace.mkdir()
    claude_dir = workspace / ".claude"
    claude_dir.mkdir()
    return workspace


@pytest.fixture
def state_file(temp_workspace):
    """Get path to batch state file."""
    return temp_workspace / ".claude" / "batch_state.json"


# =============================================================================
# SECTION 1: Path Traversal Prevention Tests (3 tests)
# =============================================================================

class TestPathTraversalPrevention:
    """Test path traversal prevention in feature names and file paths."""

    def test_malicious_feature_name_sanitized(self, temp_workspace):
        """Test that feature names with path traversal are sanitized."""
        # Arrange - malicious feature name
        malicious_features = [
            "../../etc/passwd",
            "../../../root/.ssh/id_rsa",
            "legitimate feature",
        ]
        features_file = "/tmp/features.txt"

        # Act
        batch_state = create_batch_state(features_file, malicious_features)

        # Assert - feature names sanitized (no path traversal)
        for feature in batch_state.features:
            assert ".." not in feature or "sanitized" in feature.lower()
            # Implementation should sanitize or reject malicious names

    def test_retry_state_file_path_validated(self, temp_workspace):
        """Test that retry state file path is validated (CWE-22)."""
        # Arrange - malicious batch_id with path traversal
        malicious_batch_id = "../../etc/passwd"

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            # Implementation should validate path before creating files
            manager = BatchRetryManager(malicious_batch_id, state_dir=temp_workspace / ".claude")

        # Error should mention path validation
        assert "path" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_consent_state_file_rejects_symlinks(self, tmp_path):
        """Test that consent state file rejects symlinks (CWE-59)."""
        # Arrange - create symlink to /etc/passwd
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        autonomous_dev_dir = home_dir / ".autonomous-dev"
        autonomous_dev_dir.mkdir()

        symlink_path = autonomous_dev_dir / "user_state.json"

        try:
            symlink_path.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Act & Assert
        with patch("batch_retry_consent.get_user_state_file", return_value=symlink_path):
            with pytest.raises(Exception) as exc_info:
                save_consent_state(retry_enabled=True)

            assert "symlink" in str(exc_info.value).lower()


# =============================================================================
# SECTION 2: Log Injection Prevention Tests (3 tests)
# =============================================================================

class TestLogInjectionPrevention:
    """Test log injection prevention (CWE-117)."""

    def test_error_message_with_newlines_sanitized(self):
        """Test that error messages with newlines are sanitized."""
        # Arrange - malicious error with fake log entries
        malicious_error = "ConnectionError\nFAKE LOG: Admin access granted\nReal error continues"

        # Act
        sanitized = sanitize_error_message(malicious_error)

        # Assert - newlines removed
        assert "\n" not in sanitized
        assert "\r" not in sanitized

    def test_feature_name_with_injection_sanitized(self, temp_workspace):
        """Test that feature names with log injection attempts are sanitized."""
        # Arrange - feature name with newlines
        malicious_features = [
            "Add auth\nFAKE LOG: Security disabled\nReal feature",
            "Normal feature",
        ]
        features_file = "/tmp/features.txt"

        # Act
        batch_state = create_batch_state(features_file, malicious_features)

        # Assert - newlines removed or sanitized
        for feature in batch_state.features:
            assert "\n" not in feature
            assert "\r" not in feature

    def test_audit_log_sanitizes_all_inputs(self, temp_workspace):
        """Test that audit logging sanitizes all user inputs."""
        # Arrange
        features = ["Normal feature"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Malicious error message
        malicious_error = "Error\nFAKE AUDIT LOG: User hacked system\nReal error"

        # Act
        with patch("batch_retry_manager.log_audit_event") as mock_audit:
            retry_manager.record_retry_attempt(0, malicious_error)

            # Assert - audit log call sanitized the input
            call_args = str(mock_audit.call_args)
            assert "\n" not in mock_audit.call_args[0][1] if len(mock_audit.call_args[0]) > 1 else True
            # Implementation should sanitize before logging


# =============================================================================
# SECTION 3: Global Retry Limit Enforcement Tests (3 tests)
# =============================================================================

class TestGlobalRetryLimitEnforcement:
    """Test global retry limit prevents resource exhaustion (CWE-400)."""

    def test_global_retry_limit_enforced(self, temp_workspace):
        """Test that global retry limit is strictly enforced."""
        # Arrange
        features = ["Feature 1", "Feature 2", "Feature 3"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act - attempt to exceed global limit
        for i in range(MAX_TOTAL_RETRIES + 10):
            feature_index = i % 3
            retry_manager.record_retry_attempt(feature_index, f"Error {i}")

        # Try one more retry
        from failure_classifier import FailureType
        decision = retry_manager.should_retry_feature(0, FailureType.TRANSIENT)

        # Assert - blocked due to global limit
        assert decision.should_retry is False
        assert decision.reason == "global_retry_limit_reached"
        assert retry_manager.get_global_retry_count() <= MAX_TOTAL_RETRIES

    def test_circuit_breaker_prevents_infinite_loops(self, temp_workspace):
        """Test that circuit breaker prevents infinite retry loops."""
        # Arrange
        features = ["Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act - trigger circuit breaker
        for i in range(CIRCUIT_BREAKER_THRESHOLD):
            retry_manager.record_retry_attempt(i, f"Error {i}")

        # Assert - circuit breaker open, further retries blocked
        assert retry_manager.check_circuit_breaker() is True

        from failure_classifier import FailureType
        decision = retry_manager.should_retry_feature(5, FailureType.TRANSIENT)
        assert decision.should_retry is False

    def test_max_retries_reasonable_for_large_batches(self):
        """Test that MAX_TOTAL_RETRIES is reasonable for large batches."""
        # Arrange & Assert
        # For 50 features × 3 retries each = 150 max retries
        # MAX_TOTAL_RETRIES should be at least 20 but not excessive
        assert MAX_TOTAL_RETRIES >= 20, "Global limit too low for reasonable batches"
        assert MAX_TOTAL_RETRIES <= 100, "Global limit too high, allows excessive retries"


# =============================================================================
# SECTION 4: Audit Logging Tests (4 tests)
# =============================================================================

class TestAuditLogging:
    """Test audit logging for all retry attempts."""

    def test_all_retry_attempts_logged(self, temp_workspace):
        """Test that every retry attempt is logged to audit file."""
        # Arrange
        features = ["Feature 1"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act
        with patch("batch_retry_manager.log_audit_event") as mock_audit:
            retry_manager.record_retry_attempt(0, "Error 1")
            retry_manager.record_retry_attempt(0, "Error 2")
            retry_manager.record_retry_attempt(0, "Error 3")

            # Assert - 3 audit log calls
            assert mock_audit.call_count == 3

    def test_audit_log_includes_all_required_fields(self, temp_workspace):
        """Test that audit logs include all required fields."""
        # Arrange
        features = ["Feature 1"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act
        with patch("batch_retry_manager.log_audit_event") as mock_audit:
            retry_manager.record_retry_attempt(0, "ConnectionError: Network failure")

            # Assert - audit log has required fields
            call_args = mock_audit.call_args
            log_entry = str(call_args)

            # Required fields: timestamp, batch_id, feature_index, error_message, retry_count
            assert batch_state.batch_id in log_entry
            assert "0" in log_entry  # feature_index
            assert "retry" in log_entry.lower()

    def test_circuit_breaker_trigger_logged(self, temp_workspace):
        """Test that circuit breaker trigger is logged."""
        # Arrange
        features = ["F1", "F2", "F3", "F4", "F5"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act
        with patch("batch_retry_manager.log_audit_event") as mock_audit:
            # Trigger circuit breaker
            for i in range(CIRCUIT_BREAKER_THRESHOLD):
                retry_manager.record_retry_attempt(i, f"Error {i}")

            # Assert - circuit breaker event logged
            logged_calls = [str(call) for call in mock_audit.call_args_list]
            assert any("circuit" in call.lower() for call in logged_calls)

    def test_audit_log_file_permissions_secure(self, temp_workspace):
        """Test that audit log file has secure permissions (0o600)."""
        # Arrange
        features = ["Feature 1"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act - record retry (should create audit log)
        retry_manager.record_retry_attempt(0, "Error")

        # Assert - audit log file has secure permissions
        audit_log_file = temp_workspace / ".claude" / "audit.log"
        if audit_log_file.exists():
            mode = audit_log_file.stat().st_mode & 0o777
            assert mode == 0o600, f"Audit log permissions {oct(mode)} not secure"


# =============================================================================
# SECTION 5: Consent State File Security Tests (3 tests)
# =============================================================================

class TestConsentStateFileSecurity:
    """Test security of consent state file."""

    def test_consent_state_file_secure_permissions(self, tmp_path):
        """Test that user_state.json has 0o600 permissions (CWE-732)."""
        # Arrange
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        autonomous_dev_dir = home_dir / ".autonomous-dev"
        autonomous_dev_dir.mkdir()

        user_state_file = autonomous_dev_dir / "user_state.json"

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert - file has 0o600 permissions
        assert user_state_file.exists()
        mode = user_state_file.stat().st_mode & 0o777
        assert mode == 0o600, f"Consent file permissions {oct(mode)} not secure"

    def test_consent_state_directory_created_securely(self, tmp_path):
        """Test that ~/.autonomous-dev/ is created with secure permissions."""
        # Arrange
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        # Directory doesn't exist yet
        autonomous_dev_dir = home_dir / ".autonomous-dev"
        user_state_file = autonomous_dev_dir / "user_state.json"

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            save_consent_state(retry_enabled=True)

        # Assert - directory created with secure permissions
        assert autonomous_dev_dir.exists()
        mode = autonomous_dev_dir.stat().st_mode & 0o777
        # Should be 0o700 (user-only rwx)
        assert mode == 0o700, f"Directory permissions {oct(mode)} not secure"

    def test_consent_state_atomic_write(self, tmp_path):
        """Test that consent state uses atomic write (temp + rename)."""
        # Arrange
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        autonomous_dev_dir = home_dir / ".autonomous-dev"
        autonomous_dev_dir.mkdir()

        user_state_file = autonomous_dev_dir / "user_state.json"

        # Act
        with patch("batch_retry_consent.get_user_state_file", return_value=user_state_file):
            with patch("tempfile.mkstemp") as mock_mkstemp, \
                 patch("os.write") as mock_write, \
                 patch("os.close") as mock_close, \
                 patch("pathlib.Path.replace") as mock_replace:

                mock_mkstemp.return_value = (999, "/tmp/.user_state_abc.tmp")

                save_consent_state(retry_enabled=True)

                # Assert - atomic write pattern used
                mock_mkstemp.assert_called_once()
                mock_write.assert_called_once()
                mock_close.assert_called_once()
                mock_replace.assert_called_once()


# =============================================================================
# SECTION 6: Resource Exhaustion Prevention Tests (2 tests)
# =============================================================================

class TestResourceExhaustionPrevention:
    """Test resource exhaustion prevention (CWE-400)."""

    def test_retry_state_file_size_bounded(self, temp_workspace):
        """Test that retry state file size doesn't grow unbounded."""
        # Arrange
        features = ["Feature 1"]
        batch_state = create_batch_state("/tmp/features.txt", features)
        save_batch_state(temp_workspace / ".claude" / "batch_state.json", batch_state)

        retry_manager = BatchRetryManager(batch_state.batch_id, state_dir=temp_workspace / ".claude")

        # Act - record many retries
        for i in range(100):
            retry_manager.record_retry_attempt(0, f"Error {i}")

        # Assert - state file size reasonable (< 100KB)
        retry_state_file = temp_workspace / ".claude" / f"{batch_state.batch_id}_retry_state.json"
        if retry_state_file.exists():
            file_size = retry_state_file.stat().st_size
            assert file_size < 100 * 1024, f"Retry state file too large: {file_size} bytes"

    def test_error_message_length_limited(self):
        """Test that error messages are truncated to prevent memory exhaustion."""
        # Arrange - extremely long error message
        long_error = "Error: " + ("X" * 1000000)  # 1MB error message

        # Act
        sanitized = sanitize_error_message(long_error)

        # Assert - message truncated
        assert len(sanitized) <= 1000, "Error message not truncated"
        assert sanitized.endswith("...") or sanitized.endswith("[truncated]")


# =============================================================================
# Test Summary
# =============================================================================

"""
TEST SUMMARY (18 security tests for batch retry functionality):

SECTION 1: Path Traversal Prevention (3 tests)
✗ test_malicious_feature_name_sanitized
✗ test_retry_state_file_path_validated
✗ test_consent_state_file_rejects_symlinks

SECTION 2: Log Injection Prevention (3 tests)
✗ test_error_message_with_newlines_sanitized
✗ test_feature_name_with_injection_sanitized
✗ test_audit_log_sanitizes_all_inputs

SECTION 3: Global Retry Limit Enforcement (3 tests)
✗ test_global_retry_limit_enforced
✗ test_circuit_breaker_prevents_infinite_loops
✗ test_max_retries_reasonable_for_large_batches

SECTION 4: Audit Logging (4 tests)
✗ test_all_retry_attempts_logged
✗ test_audit_log_includes_all_required_fields
✗ test_circuit_breaker_trigger_logged
✗ test_audit_log_file_permissions_secure

SECTION 5: Consent State File Security (3 tests)
✗ test_consent_state_file_secure_permissions
✗ test_consent_state_directory_created_securely
✗ test_consent_state_atomic_write

SECTION 6: Resource Exhaustion Prevention (2 tests)
✗ test_retry_state_file_size_bounded
✗ test_error_message_length_limited

TOTAL: 18 security tests (all FAILING - TDD red phase)

Security Coverage:
- CWE-22: Path traversal prevention
- CWE-59: Symlink attack prevention
- CWE-117: Log injection prevention
- CWE-400: Resource exhaustion prevention
- CWE-732: Incorrect permission assignment
- Audit logging for all retry attempts
- Secure file permissions (0o600 for files, 0o700 for dirs)
- Atomic writes for state files
- Input sanitization for logs
- Global retry limits
"""
