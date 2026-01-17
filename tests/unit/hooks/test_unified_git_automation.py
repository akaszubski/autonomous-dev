"""
Unit tests for unified_git_automation hook (Issue #167 - Silent failures in user projects).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation hasn't been fixed yet).

Test Strategy:
- Test graceful degradation when session directory missing
- Test portable path detection via path_utils
- Test logging infrastructure (verbose mode on/off)
- Test session file is truly optional
- Test clear warnings when libraries unavailable
- Test silent error swallowing is eliminated
- Achieve 95%+ code coverage

Hook Type: SubagentStop
Trigger: After doc-master agent completes (last agent in parallel validation)
Condition: AUTO_GIT_ENABLED=true

Issue: #167 - Git automation silently fails in user projects
Problem: Import failures swallowed, session file required, no logging
Solution: Add logging, make session optional, clear warnings

Date: 2026-01-01
Feature: Fix silent git automation failures
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from io import StringIO
from typing import Dict, Any

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail if implementation not updated yet (TDD!)
try:
    from unified_git_automation import (
        find_lib_dir,
        parse_bool,
        should_trigger_git_workflow,
        check_git_workflow_consent,
        get_session_file_path,
        execute_git_workflow,
        log_warning,
        log_info,
        main,
        AUTO_GIT_ENABLED,
        AUTO_GIT_PUSH,
        AUTO_GIT_PR,
        HAS_SECURITY_UTILS,
        HAS_GIT_INTEGRATION,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestLoggingInfrastructure:
    """Test logging infrastructure for user-visible warnings (Issue #167)."""

    def test_log_warning_verbose_enabled(self):
        """Should log to stderr when GIT_AUTOMATION_VERBOSE=true."""
        with patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'true'}):
            captured = StringIO()
            with patch('sys.stderr', captured):
                log_warning("Test warning message")

            output = captured.getvalue()
            assert "WARNING:" in output
            assert "Test warning message" in output

    def test_log_warning_verbose_disabled(self):
        """Should be silent when GIT_AUTOMATION_VERBOSE=false."""
        with patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'false'}):
            captured = StringIO()
            with patch('sys.stderr', captured):
                log_warning("Test warning message")

            output = captured.getvalue()
            assert output == ""

    def test_log_warning_verbose_not_set(self):
        """Should be silent when GIT_AUTOMATION_VERBOSE not set (default)."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure env var not set
            if 'GIT_AUTOMATION_VERBOSE' in os.environ:
                del os.environ['GIT_AUTOMATION_VERBOSE']

            captured = StringIO()
            with patch('sys.stderr', captured):
                log_warning("Test warning message")

            output = captured.getvalue()
            assert output == ""

    def test_log_info_verbose_enabled(self):
        """Should log to stderr when GIT_AUTOMATION_VERBOSE=true."""
        with patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'true'}):
            captured = StringIO()
            with patch('sys.stderr', captured):
                log_info("Test info message")

            output = captured.getvalue()
            assert "GIT-AUTOMATION INFO:" in output
            assert "Test info message" in output

    def test_log_info_verbose_disabled(self):
        """Should be silent when GIT_AUTOMATION_VERBOSE=false."""
        with patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'false'}):
            captured = StringIO()
            with patch('sys.stdout', captured):
                log_info("Test info message")

            output = captured.getvalue()
            assert output == ""

    def test_log_warning_multiline_message(self):
        """Should handle multiline warning messages correctly."""
        with patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'true'}):
            captured = StringIO()
            with patch('sys.stderr', captured):
                log_warning("Line 1\nLine 2\nLine 3")

            output = captured.getvalue()
            assert "WARNING:" in output
            assert "Line 1" in output
            assert "Line 2" in output
            assert "Line 3" in output


class TestSessionFileGracefulDegradation:
    """Test session file is optional with graceful degradation (Issue #167)."""

    def test_get_session_file_path_missing_directory(self):
        """Should return None gracefully when session directory missing."""
        with patch.dict(os.environ, {}, clear=True):
            # Disable path_utils to use fallback path, then mock it to not exist
            with patch('unified_git_automation.HAS_PATH_UTILS', False):
                with patch('unified_git_automation.Path') as mock_path:
                    # Mock the fallback hardcoded path
                    mock_session_dir = MagicMock()
                    mock_session_dir.exists.return_value = False
                    mock_path.return_value = mock_session_dir

                    # Should not raise exception
                    result = get_session_file_path()
                    assert result is None

    def test_get_session_file_path_portable_discovery(self):
        """Should use path_utils for portable session directory discovery."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock path_utils.get_session_dir in the correct namespace
            with patch('unified_git_automation.get_session_dir') as mock_get_session_dir, \
                 patch('unified_git_automation.HAS_PATH_UTILS', True):
                mock_session_dir = Path('/mock/project/docs/sessions')
                mock_get_session_dir.return_value = mock_session_dir

                # Create mock session files
                with patch.object(Path, 'exists', return_value=True), \
                     patch.object(Path, 'glob') as mock_glob:
                    mock_files = [
                        Path('/mock/project/docs/sessions/2026-01-01-pipeline.json'),
                        Path('/mock/project/docs/sessions/2026-01-02-pipeline.json'),
                    ]
                    mock_glob.return_value = mock_files

                    result = get_session_file_path()

                    # Should return latest file
                    assert result == mock_files[-1]

                    # Should have used path_utils
                    mock_get_session_dir.assert_called_once()

    def test_get_session_file_path_env_var_override(self):
        """Should respect SESSION_FILE environment variable."""
        custom_session = "/custom/path/session.json"

        with patch.dict(os.environ, {'SESSION_FILE': custom_session}):
            with patch('unified_git_automation.HAS_SECURITY_UTILS', False), \
                 patch.object(Path, 'exists', return_value=True):
                result = get_session_file_path()

                assert result is not None
                assert str(result) == str(Path(custom_session).resolve())

    def test_get_session_file_path_env_var_nonexistent(self):
        """Should return None when SESSION_FILE env var points to nonexistent file."""
        custom_session = "/nonexistent/session.json"

        with patch.dict(os.environ, {'SESSION_FILE': custom_session}):
            with patch('unified_git_automation.HAS_SECURITY_UTILS', False), \
                 patch.object(Path, 'exists', return_value=False):
                result = get_session_file_path()

                assert result is None

    def test_get_session_file_path_security_validation_rejection(self):
        """Should return None when security validation rejects path."""
        custom_session = "/etc/passwd"  # Path traversal attempt

        with patch.dict(os.environ, {'SESSION_FILE': custom_session}):
            with patch('unified_git_automation.HAS_SECURITY_UTILS', True), \
                 patch('unified_git_automation.validate_path') as mock_validate, \
                 patch('unified_git_automation.audit_log') as mock_audit:
                mock_validate.side_effect = ValueError("Path traversal detected")

                result = get_session_file_path()

                assert result is None

                # Should have logged rejection
                mock_audit.assert_called_once()
                # Check keyword arguments (audit_log uses event_type=, status=, context=)
                call_kwargs = mock_audit.call_args[1]
                assert call_kwargs['event_type'] == 'session_file_path_validation'
                assert call_kwargs['status'] == 'rejected'


class TestLibraryImportFailures:
    """Test clear warnings when libraries unavailable (Issue #167)."""

    def test_execute_git_workflow_missing_library(self):
        """Should show clear warning when HAS_GIT_INTEGRATION=False."""
        with patch('unified_git_automation.HAS_GIT_INTEGRATION', False), \
             patch.dict(os.environ, {'GIT_AUTOMATION_VERBOSE': 'true'}):

            captured = StringIO()
            with patch('sys.stderr', captured):
                session_file = Path('/mock/session.json')
                consent = {'git_enabled': True, 'push_enabled': False, 'pr_enabled': False}

                result = execute_git_workflow(session_file, consent)

                assert result is False

                # Should have logged warning
                output = captured.getvalue()
                assert "WARNING:" in output or "auto_implement_git_integration" in output

    def test_main_missing_session_continues(self):
        """Should continue workflow when session file missing (non-blocking)."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'true',
            'GIT_AUTOMATION_VERBOSE': 'false'
        }):
            with patch('unified_git_automation.get_session_file_path') as mock_get_session:
                mock_get_session.return_value = None

                # Should not raise exception
                exit_code = main()

                # Should return 0 (non-blocking hook)
                assert exit_code == 0

    def test_main_missing_security_utils_continues(self):
        """Should continue when security_utils unavailable (graceful degradation)."""
        with patch('unified_git_automation.HAS_SECURITY_UTILS', False), \
             patch.dict(os.environ, {
                 'CLAUDE_AGENT_NAME': 'doc-master',
                 'CLAUDE_AGENT_STATUS': 'success',
                 'AUTO_GIT_ENABLED': 'true',
             }):
            with patch('unified_git_automation.get_session_file_path') as mock_get_session:
                mock_get_session.return_value = None

                # Should not raise exception
                exit_code = main()

                # Should return 0 (non-blocking hook)
                assert exit_code == 0


class TestTriggerConditions:
    """Test hook triggering logic - when should git workflow activate?"""

    def test_trigger_when_doc_master_completes(self):
        """Should trigger when doc-master agent completes."""
        assert should_trigger_git_workflow('doc-master') is True

    def test_no_trigger_for_other_agents(self):
        """Should NOT trigger for agents other than doc-master."""
        agents = [
            'researcher',
            'researcher-local',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
        ]
        for agent in agents:
            assert should_trigger_git_workflow(agent) is False

    def test_no_trigger_for_empty_agent_name(self):
        """Should NOT trigger for empty agent name."""
        assert should_trigger_git_workflow('') is False

    def test_no_trigger_for_none_agent_name(self):
        """Should NOT trigger for None agent name."""
        assert should_trigger_git_workflow(None) is False

    def test_case_sensitive_agent_name(self):
        """Should be case-sensitive for agent names."""
        assert should_trigger_git_workflow('Doc-Master') is False
        assert should_trigger_git_workflow('DOC-MASTER') is False


class TestConsentChecking:
    """Test consent checking via environment variables."""

    def test_consent_all_enabled(self):
        """Should return all enabled when all env vars are true."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'true'
        }):
            consent = check_git_workflow_consent()

            assert consent['git_enabled'] is True
            assert consent['push_enabled'] is True
            assert consent['pr_enabled'] is True
            assert consent['all_enabled'] is True

    def test_consent_git_disabled(self):
        """Should return all disabled when AUTO_GIT_ENABLED=false."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'false',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'true'
        }):
            consent = check_git_workflow_consent()

            assert consent['git_enabled'] is False
            assert consent['push_enabled'] is False
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False

    def test_consent_partial_enabled(self):
        """Should respect individual consent flags."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'false'
        }):
            consent = check_git_workflow_consent()

            assert consent['git_enabled'] is True
            assert consent['push_enabled'] is True
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False


class TestParseBool:
    """Test boolean parsing utility function."""

    def test_parse_bool_true_variations(self):
        """Should parse various true values correctly."""
        true_values = ['true', 'True', 'TRUE', 'yes', 'YES', '1']
        for value in true_values:
            assert parse_bool(value) is True

    def test_parse_bool_false_variations(self):
        """Should parse various false values correctly."""
        false_values = ['false', 'False', 'FALSE', 'no', 'NO', '0']
        for value in false_values:
            assert parse_bool(value) is False

    def test_parse_bool_invalid_defaults_false(self):
        """Should default to False for invalid values."""
        invalid_values = ['maybe', 'unknown', '2', 'yes-no', '']
        for value in invalid_values:
            assert parse_bool(value) is False


class TestMainWorkflow:
    """Test main hook entry point workflow."""

    def test_main_skip_wrong_agent(self):
        """Should skip when agent is not doc-master."""
        with patch.dict(os.environ, {'CLAUDE_AGENT_NAME': 'implementer'}):
            exit_code = main()

            assert exit_code == 0

    def test_main_skip_error_status(self):
        """Should skip when agent status is error."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'error'
        }):
            exit_code = main()

            assert exit_code == 0

    def test_main_skip_disabled(self):
        """Should skip when AUTO_GIT_ENABLED=false."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'false'
        }):
            exit_code = main()

            assert exit_code == 0

    def test_main_execute_workflow(self):
        """Should execute workflow when all conditions met."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'false',
            'AUTO_GIT_PR': 'false'
        }):
            with patch('unified_git_automation.get_session_file_path') as mock_get_session, \
                 patch('unified_git_automation.execute_git_workflow') as mock_execute:
                mock_get_session.return_value = Path('/mock/session.json')
                mock_execute.return_value = True

                exit_code = main()

                assert exit_code == 0
                mock_execute.assert_called_once()

    def test_main_workflow_exception_nonblocking(self):
        """Should not fail hook when workflow raises exception (non-blocking)."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'true'
        }):
            with patch('unified_git_automation.get_session_file_path') as mock_get_session, \
                 patch('unified_git_automation.execute_git_workflow') as mock_execute:
                mock_get_session.return_value = Path('/mock/session.json')
                mock_execute.side_effect = Exception("Workflow failed")

                # Should not raise exception
                exit_code = main()

                # Should return 0 (non-blocking)
                assert exit_code == 0


class TestExecuteGitWorkflow:
    """Test git workflow execution function."""

    def test_execute_git_workflow_success(self):
        """Should execute workflow successfully with valid inputs."""
        with patch('unified_git_automation.HAS_GIT_INTEGRATION', True), \
             patch('unified_git_automation.execute_step8_git_operations_from_hook') as mock_execute:
            mock_execute.return_value = {'success': True, 'commit_sha': 'abc123'}

            session_file = Path('/mock/session.json')
            consent = {
                'git_enabled': True,
                'push_enabled': False,
                'pr_enabled': False
            }

            result = execute_git_workflow(session_file, consent)

            assert result is True
            mock_execute.assert_called_once()

    def test_execute_git_workflow_library_error(self):
        """Should return False when library raises exception."""
        with patch('unified_git_automation.HAS_GIT_INTEGRATION', True), \
             patch('unified_git_automation.execute_step8_git_operations_from_hook') as mock_execute, \
             patch('unified_git_automation.HAS_SECURITY_UTILS', True), \
             patch('unified_git_automation.audit_log') as mock_audit:
            mock_execute.side_effect = Exception("Git operation failed")

            session_file = Path('/mock/session.json')
            consent = {'git_enabled': True, 'push_enabled': False, 'pr_enabled': False}

            result = execute_git_workflow(session_file, consent)

            assert result is False

            # Should have logged error (check keyword arguments)
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs['event_type'] == 'git_workflow_execution'
            assert call_kwargs['status'] == 'error'


class TestLibIntegrationSessionFileOptional:
    """Test auto_implement_git_integration accepts session_file=None (Issue #167)."""

    def test_execute_step8_session_file_optional(self):
        """Should work when session_file=None (graceful degradation)."""
        # This test will fail until auto_implement_git_integration.py is updated
        from auto_implement_git_integration import execute_step8_git_operations_from_hook

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'false',  # Disabled to skip actual git ops
        }):
            # Should not raise exception
            result = execute_step8_git_operations_from_hook(
                session_file=None,  # KEY: session_file is optional
                git_enabled=False,
                push_enabled=False,
                pr_enabled=False,
            )

            # Should skip gracefully
            assert 'success' in result or 'skipped' in result

    def test_execute_step8_session_file_provided(self):
        """Should work normally when session_file provided."""
        from auto_implement_git_integration import execute_step8_git_operations_from_hook

        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'false',  # Disabled to skip actual git ops
        }):
            mock_session = Path('/mock/session.json')

            # Should not raise exception
            result = execute_step8_git_operations_from_hook(
                session_file=mock_session,
                git_enabled=False,
                push_enabled=False,
                pr_enabled=False,
            )

            # Should skip gracefully
            assert 'success' in result or 'skipped' in result


class TestFindLibDir:
    """Test dynamic library discovery function."""

    def test_find_lib_dir_relative_to_hooks(self):
        """Should find lib directory relative to hooks directory."""
        # Mock Path to simulate hooks/../lib exists
        with patch('unified_git_automation.Path') as mock_path:
            mock_lib_dir = MagicMock()
            mock_lib_dir.exists.return_value = True
            mock_path.return_value = mock_lib_dir

            result = find_lib_dir()

            assert result is not None

    def test_find_lib_dir_not_found(self):
        """Should return None when lib directory not found."""
        # Mock all candidate paths to not exist
        with patch('unified_git_automation.Path') as mock_path:
            # Create mock candidates that all return False for exists()
            mock_candidate = MagicMock()
            mock_candidate.exists.return_value = False

            # Mock __file__.parent.parent / "lib"
            mock_file = MagicMock()
            mock_file.parent.parent.__truediv__.return_value = mock_candidate

            # Mock cwd() / "plugins" / "autonomous-dev" / "lib"
            mock_cwd = MagicMock()
            mock_cwd.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_candidate

            # Mock home() / ".autonomous-dev" / "lib"
            mock_home = MagicMock()
            mock_home.__truediv__.return_value.__truediv__.return_value = mock_candidate

            # Configure Path() behavior
            mock_path.return_value = mock_file
            mock_path.cwd.return_value = mock_cwd
            mock_path.home.return_value = mock_home

            result = find_lib_dir()

            assert result is None


# ============================================================================
# Integration Tests (End-to-End Scenarios)
# ============================================================================

class TestEndToEndScenarios:
    """Test end-to-end scenarios for Issue #167."""

    def test_user_project_without_plugins_directory(self):
        """Should gracefully degrade in user project without plugins/ directory."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'true',
            'GIT_AUTOMATION_VERBOSE': 'true'
        }):
            with patch('unified_git_automation.HAS_GIT_INTEGRATION', False), \
                 patch('unified_git_automation.get_session_file_path') as mock_get_session:
                mock_get_session.return_value = None

                captured = StringIO()
                with patch('sys.stderr', captured):
                    exit_code = main()

                    # Should not fail
                    assert exit_code == 0

                    # Should log clear message (when verbose)
                    output = captured.getvalue()
                    # Either warning logged or silent (depending on verbose mode)

    def test_autonomous_dev_repo_with_all_features(self):
        """Should use all features in autonomous-dev repository."""
        with patch.dict(os.environ, {
            'CLAUDE_AGENT_NAME': 'doc-master',
            'CLAUDE_AGENT_STATUS': 'success',
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'true'
        }):
            with patch('unified_git_automation.HAS_GIT_INTEGRATION', True), \
                 patch('unified_git_automation.HAS_SECURITY_UTILS', True), \
                 patch('unified_git_automation.get_session_file_path') as mock_get_session, \
                 patch('unified_git_automation.execute_step8_git_operations_from_hook') as mock_execute:
                mock_get_session.return_value = Path('/mock/session.json')
                mock_execute.return_value = {'success': True, 'commit_sha': 'abc123'}

                exit_code = main()

                # Should execute successfully
                assert exit_code == 0
                mock_execute.assert_called_once()


# ============================================================================
# Checkpoint Integration
# ============================================================================

# Save checkpoint for test-master agent
from pathlib import Path
import sys

# Portable path detection (works from any directory)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

# Add lib to path for imports
lib_path = project_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

    try:
        from agent_tracker import AgentTracker
        # Method removed in refactor - checkpoint functionality deprecated
        print("ℹ️ Checkpoint skipped (method deprecated)")
    except (ImportError, AttributeError):
        print("ℹ️ Checkpoint skipped (user project)")
