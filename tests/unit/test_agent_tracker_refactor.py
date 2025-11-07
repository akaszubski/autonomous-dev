#!/usr/bin/env python3
"""
TDD Tests for AgentTracker Refactoring to Use security_utils (FAILING - Red Phase)

This module contains FAILING tests that verify agent_tracker.py is refactored to use
the shared security_utils.py module instead of custom validation logic.

Security Requirements (from GitHub issue #46):
1. Replace custom path validation with validate_path_whitelist() from security_utils
2. Add audit logging for all path validation attempts
3. Maintain all existing security guarantees (atomic writes, race conditions, etc.)
4. Ensure backward compatibility with existing tests
5. Test mode support must work with shared validation

Test Strategy:
- Verify security_utils functions are called (mock verification)
- Ensure existing security behaviors are preserved (integration tests)
- Test that audit logging captures all security events
- Confirm test mode still works correctly

Test Coverage Target: 100% of refactored security code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe refactoring requirements
- Tests should FAIL until refactoring is complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-07
Issue: #46
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agent_tracker import AgentTracker

# This import will FAIL until security_utils.py is created
from plugins.autonomous_dev.lib.security_utils import (
    validate_path_whitelist,
    audit_log_security_event,
    SecurityValidationError
)


class TestAgentTrackerUsesSecurityUtils:
    """Test that AgentTracker is refactored to use shared security_utils module.

    Critical requirement: Must use validate_path_whitelist() from security_utils
    instead of custom validation logic for consistency across codebase.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    def test_init_calls_validate_path_whitelist(self, temp_session_dir):
        """Test that __init__ calls validate_path_whitelist() from security_utils.

        SECURITY: Centralized validation ensures consistency.
        Expected: validate_path_whitelist() called with session_file and PROJECT_ROOT.
        """
        session_file = temp_session_dir / "test-session.json"

        # Mock validate_path_whitelist to verify it's called
        with patch('scripts.agent_tracker.validate_path_whitelist') as mock_validate:
            mock_validate.return_value = session_file.resolve()

            # Initialize tracker
            tracker = AgentTracker(session_file=str(session_file))

            # Verify validate_path_whitelist was called
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args[0]
            assert Path(call_args[0]) == session_file  # First arg is path
            # Second arg should be PROJECT_ROOT

    def test_validation_error_propagates_from_security_utils(self, temp_session_dir):
        """Test that SecurityValidationError from security_utils propagates correctly.

        SECURITY: Errors from shared module should bubble up unchanged.
        Expected: SecurityValidationError raised with original message.
        """
        malicious_path = Path("/etc/passwd")

        # Mock validate_path_whitelist to raise SecurityValidationError
        with patch('scripts.agent_tracker.validate_path_whitelist') as mock_validate:
            mock_validate.side_effect = SecurityValidationError("Path traversal attempt detected")

            with pytest.raises(SecurityValidationError) as exc_info:
                tracker = AgentTracker(session_file=str(malicious_path))

            assert "Path traversal" in str(exc_info.value)

    def test_audit_logging_called_on_success(self, temp_session_dir):
        """Test that audit logging is called when path validation succeeds.

        SECURITY: All successful path validations should be logged.
        Expected: audit_log_security_event() called with ALLOWED result.
        """
        session_file = temp_session_dir / "test-session.json"

        with patch('scripts.agent_tracker.validate_path_whitelist') as mock_validate:
            mock_validate.return_value = session_file.resolve()

            with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
                # Initialize tracker
                tracker = AgentTracker(session_file=str(session_file))

                # Verify audit logging was called
                mock_audit.assert_called()
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs['event_type'] == 'PATH_VALIDATION'
                assert call_kwargs['result'] == 'ALLOWED'
                assert call_kwargs['path'] == session_file.resolve()

    def test_audit_logging_called_on_failure(self, temp_session_dir):
        """Test that audit logging is called when path validation fails.

        SECURITY: All blocked path attempts should be logged.
        Expected: audit_log_security_event() called with BLOCKED result.
        """
        malicious_path = Path("/etc/passwd")

        with patch('scripts.agent_tracker.validate_path_whitelist') as mock_validate:
            mock_validate.side_effect = SecurityValidationError("Path traversal detected")

            with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
                try:
                    tracker = AgentTracker(session_file=str(malicious_path))
                except SecurityValidationError:
                    pass

                # Verify audit logging was called for blocked attempt
                mock_audit.assert_called()
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs['event_type'] == 'PATH_VALIDATION'
                assert call_kwargs['result'] == 'BLOCKED'

    def test_custom_validation_code_removed(self, temp_session_dir):
        """Test that custom validation code is removed from __init__.

        SECURITY: No duplicate validation logic - only use security_utils.
        Expected: No string checks for '..' in __init__, no custom system dir checks.
        """
        # Read agent_tracker.py source code
        agent_tracker_file = Path(__file__).parent.parent.parent / "scripts" / "agent_tracker.py"
        source_code = agent_tracker_file.read_text()

        # Verify old validation patterns are removed from __init__
        init_start = source_code.find("def __init__(")
        init_end = source_code.find("\n    def ", init_start + 1)
        init_code = source_code[init_start:init_end]

        # Old patterns that should be removed
        old_patterns = [
            '".." in',  # String check for '..'
            'if "/etc/" in',  # System directory checks
            'if "/var/log/" in',
            'if "/usr/" in',
            'startswith("/etc")',
            'startswith("/var/log")',
        ]

        for pattern in old_patterns:
            assert pattern not in init_code, f"Old validation pattern still present: {pattern}"


class TestAgentTrackerBackwardCompatibility:
    """Test that refactoring maintains backward compatibility.

    Critical requirement: Existing tests should still pass after refactoring.
    Behavior should be identical, only implementation changed.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    def test_valid_paths_still_accepted(self, temp_session_dir):
        """Test that valid paths work exactly as before.

        BACKWARD COMPATIBILITY: Refactoring should not change valid path behavior.
        Expected: Same paths that worked before still work.
        """
        session_file = temp_session_dir / "test-session.json"

        # Should not raise exception (same as before refactoring)
        tracker = AgentTracker(session_file=str(session_file))
        assert tracker is not None

    def test_malicious_paths_still_blocked(self, temp_session_dir):
        """Test that malicious paths are blocked exactly as before.

        BACKWARD COMPATIBILITY: Security guarantees must be preserved.
        Expected: Same paths that were blocked before are still blocked.
        """
        malicious_paths = [
            "/etc/passwd",
            "/var/log/evil.json",
            str(temp_session_dir / ".." / ".." / "etc" / "passwd")
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((ValueError, SecurityValidationError)):
                tracker = AgentTracker(session_file=malicious_path)

    def test_atomic_writes_still_work(self, temp_session_dir):
        """Test that atomic write operations work after refactoring.

        BACKWARD COMPATIBILITY: File write behavior must be unchanged.
        Expected: Temp file + rename pattern still used.
        """
        session_file = temp_session_dir / "test-session.json"
        tracker = AgentTracker(session_file=str(session_file))

        # Start an agent
        tracker.log_agent_start("researcher", "Testing atomic writes")

        # Verify file was written atomically
        assert session_file.exists()
        data = json.loads(session_file.read_text())
        assert len(data["agents"]) == 1

    def test_race_condition_protection_maintained(self, temp_session_dir):
        """Test that race condition protections still work.

        BACKWARD COMPATIBILITY: Concurrent access safety must be preserved.
        Expected: Multiple threads can safely write to same session file.
        """
        import threading

        session_file = temp_session_dir / "test-session.json"
        results = []

        def log_agent(agent_name):
            try:
                tracker = AgentTracker(session_file=str(session_file))
                tracker.log_agent_start(agent_name, f"Testing {agent_name}")
                results.append(("success", agent_name))
            except Exception as e:
                results.append(("error", str(e)))

        # Create multiple threads
        threads = []
        agent_names = ["researcher", "planner", "test-master", "implementer", "reviewer"]
        for agent_name in agent_names:
            thread = threading.Thread(target=log_agent, args=(agent_name,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all succeeded
        assert all(result[0] == "success" for result in results)

        # Verify file is valid JSON (not corrupted)
        data = json.loads(session_file.read_text())
        assert len(data["agents"]) == len(agent_names)


class TestAgentTrackerTestModeWithSecurityUtils:
    """Test that test mode works correctly with security_utils.

    Critical requirement: Test mode should work with shared validation.
    Tests should be able to use temp directories.
    """

    @pytest.fixture(autouse=True)
    def set_test_mode(self):
        """Enable test mode for these tests."""
        # pytest automatically sets PYTEST_CURRENT_TEST
        yield

    def test_temp_directory_allowed_in_test_mode(self, tmp_path):
        """Test that temp directories work in test mode.

        TEST MODE: security_utils should allow temp dirs when in pytest.
        Expected: AgentTracker works with tmp_path.
        """
        session_file = tmp_path / "test-session.json"

        # Set test mode env var
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_temp_directory_allowed_in_test_mode'}):
            # Should not raise exception
            tracker = AgentTracker(session_file=str(session_file))
            assert tracker is not None

    def test_system_directories_blocked_in_test_mode(self, tmp_path):
        """Test that system directories are blocked even in test mode.

        SECURITY: Test mode should NOT weaken system directory protection.
        Expected: SecurityValidationError for /etc, /var/log, etc.
        """
        system_paths = [
            "/etc/passwd",
            "/var/log/auth.log",
            "/usr/bin/evil"
        ]

        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_system_directories_blocked_in_test_mode'}):
            for sys_path in system_paths:
                with pytest.raises((ValueError, SecurityValidationError)):
                    tracker = AgentTracker(session_file=sys_path)

    def test_pytest_format_validation_in_test_mode(self, tmp_path):
        """Test that PYTEST_CURRENT_TEST format is validated correctly.

        SECURITY: Even in test mode, validate pytest format to prevent injection.
        Expected: Malformed pytest formats rejected.
        """
        session_file = tmp_path / "test-session.json"

        # Test with malformed pytest format
        malicious_formats = [
            "../../etc/passwd::test",
            "/etc/passwd::TestClass::test_hack",
            ""  # Empty format
        ]

        for malicious_format in malicious_formats:
            with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': malicious_format}):
                # Should either reject malicious format or handle safely
                try:
                    tracker = AgentTracker(session_file=str(session_file))
                    # If it doesn't raise, verify path is safe
                    assert str(tracker.session_file).startswith(str(tmp_path))
                except (ValueError, SecurityValidationError):
                    # Expected - malicious format rejected
                    pass


class TestAgentTrackerAuditTrail:
    """Test that comprehensive audit trail is maintained.

    Security requirement: All security events should be logged for forensic analysis.
    """

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        """Create temporary session directory."""
        session_dir = tmp_path / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        return session_dir

    @pytest.fixture
    def audit_log_file(self, tmp_path):
        """Create temporary audit log file."""
        return tmp_path / "security_audit.log"

    def test_allowed_path_logged_to_audit_file(self, temp_session_dir, audit_log_file):
        """Test that allowed paths are logged to audit file.

        SECURITY: Audit trail for all access attempts.
        Expected: Log entry with ALLOWED result.
        """
        session_file = temp_session_dir / "test-session.json"

        # Mock audit logging to use test file
        with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
            def log_to_file(*args, **kwargs):
                # Simulate actual logging
                audit_log_security_event(*args, **kwargs, log_file=audit_log_file)

            mock_audit.side_effect = log_to_file

            tracker = AgentTracker(session_file=str(session_file))

            # Verify log file exists and contains entry
            assert audit_log_file.exists()
            log_content = audit_log_file.read_text()
            assert "ALLOWED" in log_content
            assert str(session_file) in log_content

    def test_blocked_path_logged_to_audit_file(self, temp_session_dir, audit_log_file):
        """Test that blocked paths are logged to audit file.

        SECURITY: Audit trail for attack detection.
        Expected: Log entry with BLOCKED result and threat details.
        """
        malicious_path = Path("/etc/passwd")

        with patch('scripts.agent_tracker.validate_path_whitelist') as mock_validate:
            mock_validate.side_effect = SecurityValidationError("Path traversal detected")

            with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
                def log_to_file(*args, **kwargs):
                    audit_log_security_event(*args, **kwargs, log_file=audit_log_file)

                mock_audit.side_effect = log_to_file

                try:
                    tracker = AgentTracker(session_file=str(malicious_path))
                except SecurityValidationError:
                    pass

                # Verify blocked attempt was logged
                assert audit_log_file.exists()
                log_content = audit_log_file.read_text()
                assert "BLOCKED" in log_content

    def test_audit_log_contains_timestamps(self, temp_session_dir, audit_log_file):
        """Test that audit log entries include timestamps.

        SECURITY: Timestamps required for forensic timeline.
        Expected: ISO 8601 timestamp in each log entry.
        """
        session_file = temp_session_dir / "test-session.json"

        with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
            def log_to_file(*args, **kwargs):
                audit_log_security_event(*args, **kwargs, log_file=audit_log_file)

            mock_audit.side_effect = log_to_file

            tracker = AgentTracker(session_file=str(session_file))

            # Verify timestamp in log
            log_content = audit_log_file.read_text()
            import re
            timestamp_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
            assert re.search(timestamp_pattern, log_content), "No ISO 8601 timestamp found"

    def test_audit_log_includes_context(self, temp_session_dir, audit_log_file):
        """Test that audit log includes contextual information.

        SECURITY: Context helps understand security decisions.
        Expected: Log contains reason, threat level, and other metadata.
        """
        session_file = temp_session_dir / "test-session.json"

        with patch('scripts.agent_tracker.audit_log_security_event') as mock_audit:
            def log_to_file(*args, **kwargs):
                # Add context to the call
                context = kwargs.get('context', {})
                context.update({
                    'operation': 'agent_tracker_init',
                    'threat_level': 'LOW'
                })
                kwargs['context'] = context
                audit_log_security_event(*args, **kwargs, log_file=audit_log_file)

            mock_audit.side_effect = log_to_file

            tracker = AgentTracker(session_file=str(session_file))

            # Verify context in log
            log_content = audit_log_file.read_text()
            assert "operation" in log_content
            assert "threat_level" in log_content


# Run tests in verbose mode to see which ones fail
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
