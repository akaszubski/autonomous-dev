"""
Unit tests for auto_git_workflow hook (SubagentStop lifecycle).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test hook triggering logic (when to activate)
- Test consent checking via environment variables
- Test security validation (path traversal, command injection)
- Test agent invocation and YAML parsing
- Test error handling and graceful degradation
- Test audit logging
- Achieve 95%+ code coverage

Hook Type: SubagentStop
Trigger: After quality-validator agent completes (last agent in pipeline)
Condition: AUTO_GIT_ENABLED=true AND pipeline complete (7 agents)

Date: 2025-11-09
Feature: Automatic git operations integration
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError, TimeoutExpired
from typing import Dict, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Import will fail - hook doesn't exist yet (TDD!)
try:
    from auto_git_workflow import (
        should_trigger_git_workflow,
        check_git_workflow_consent,
        get_session_file_path,
        read_session_data,
        extract_workflow_metadata,
        trigger_git_operations,
        run_hook,
        main,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestTriggerConditions:
    """Test hook triggering logic - when should git workflow activate?"""

    def test_trigger_when_quality_validator_completes(self):
        """Should trigger when quality-validator agent completes."""
        assert should_trigger_git_workflow('quality-validator') is True

    def test_no_trigger_for_other_agents(self):
        """Should NOT trigger for agents other than quality-validator."""
        agents = [
            'researcher',
            'planner',
            'test-master',
            'implementer',
            'reviewer',
            'security-auditor',
            'doc-master',
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
        assert should_trigger_git_workflow('Quality-Validator') is False
        assert should_trigger_git_workflow('QUALITY-VALIDATOR') is False


class TestConsentChecking:
    """Test consent checking via environment variables."""

    def test_consent_all_enabled(self):
        """Should return all True when all env vars set to true."""
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

    def test_consent_git_only(self):
        """Should enable git only when AUTO_GIT_ENABLED=true, others false."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'false',
            'AUTO_GIT_PR': 'false'
        }, clear=True):
            consent = check_git_workflow_consent()
            assert consent['git_enabled'] is True
            assert consent['push_enabled'] is False
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False

    def test_consent_git_and_push(self):
        """Should enable git+push when both true, PR false."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'false'
        }, clear=True):
            consent = check_git_workflow_consent()
            assert consent['git_enabled'] is True
            assert consent['push_enabled'] is True
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False

    def test_consent_all_disabled(self):
        """Should return all False when AUTO_GIT_ENABLED=false."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'false',
            'AUTO_GIT_PUSH': 'true',
            'AUTO_GIT_PR': 'true'
        }, clear=True):
            consent = check_git_workflow_consent()
            assert consent['git_enabled'] is False
            assert consent['push_enabled'] is False
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False

    def test_consent_defaults_to_disabled(self):
        """Should default to all disabled when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            consent = check_git_workflow_consent()
            assert consent['git_enabled'] is False
            assert consent['push_enabled'] is False
            assert consent['pr_enabled'] is False
            assert consent['all_enabled'] is False

    def test_consent_case_insensitive(self):
        """Should parse consent values case-insensitively."""
        with patch.dict(os.environ, {
            'AUTO_GIT_ENABLED': 'TRUE',
            'AUTO_GIT_PUSH': 'Yes',
            'AUTO_GIT_PR': '1'
        }, clear=True):
            consent = check_git_workflow_consent()
            assert consent['all_enabled'] is True


class TestSessionFileHandling:
    """Test session file path resolution and reading."""

    def test_get_session_file_path_from_env(self):
        """Should resolve session file path from CLAUDE_SESSION environment variable."""
        with patch.dict(os.environ, {'CLAUDE_SESSION': '/tmp/session-123.json'}):
            path = get_session_file_path()
            assert path == Path('/tmp/session-123.json')

    def test_get_session_file_path_defaults_to_latest(self):
        """Should default to latest session file when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('pathlib.Path.glob') as mock_glob:
                mock_glob.return_value = [
                    Path('/tmp/session-1.json'),
                    Path('/tmp/session-2.json'),
                ]
                path = get_session_file_path()
                # Should pick latest (sorted by name)
                assert path == Path('/tmp/session-2.json')

    def test_get_session_file_path_validates_against_traversal(self):
        """Should reject path traversal attempts in session file path."""
        with patch.dict(os.environ, {'CLAUDE_SESSION': '../../../etc/passwd'}):
            with pytest.raises(ValueError, match='Path traversal detected'):
                get_session_file_path()

    def test_get_session_file_path_validates_against_symlinks(self):
        """Should reject symlink paths (CWE-59 protection)."""
        with patch.dict(os.environ, {'CLAUDE_SESSION': '/tmp/malicious-link.json'}):
            with patch('pathlib.Path.is_symlink', return_value=True):
                with pytest.raises(ValueError, match='Symlink not allowed'):
                    get_session_file_path()

    def test_read_session_data_success(self, tmp_path):
        """Should successfully read valid session JSON."""
        session_file = tmp_path / 'session.json'
        session_data = {
            'workflow_id': 'workflow-123',
            'agents': [
                {'agent': 'researcher', 'status': 'completed'},
                {'agent': 'planner', 'status': 'completed'},
            ],
        }
        session_file.write_text(json.dumps(session_data))

        result = read_session_data(session_file)
        assert result == session_data

    def test_read_session_data_invalid_json(self, tmp_path):
        """Should raise ValueError for malformed JSON."""
        session_file = tmp_path / 'session.json'
        session_file.write_text('not valid json {{{')

        with pytest.raises(ValueError, match='Invalid JSON in session file'):
            read_session_data(session_file)

    def test_read_session_data_file_not_found(self, tmp_path):
        """Should raise FileNotFoundError for missing session file."""
        session_file = tmp_path / 'nonexistent.json'

        with pytest.raises(FileNotFoundError, match='Session file not found'):
            read_session_data(session_file)

    def test_read_session_data_empty_file(self, tmp_path):
        """Should raise ValueError for empty session file."""
        session_file = tmp_path / 'session.json'
        session_file.write_text('')

        with pytest.raises(ValueError, match='Session file is empty'):
            read_session_data(session_file)


class TestWorkflowMetadataExtraction:
    """Test extraction of workflow metadata from session data."""

    def test_extract_workflow_metadata_success(self):
        """Should extract workflow_id and request from session data."""
        session_data = {
            'workflow_id': 'workflow-123',
            'feature_request': 'Add user authentication',
            'agents': [],
        }

        metadata = extract_workflow_metadata(session_data)
        assert metadata['workflow_id'] == 'workflow-123'
        assert metadata['request'] == 'Add user authentication'

    def test_extract_workflow_metadata_missing_workflow_id(self):
        """Should raise ValueError if workflow_id missing."""
        session_data = {
            'feature_request': 'Add authentication',
            'agents': [],
        }

        with pytest.raises(ValueError, match='workflow_id not found'):
            extract_workflow_metadata(session_data)

    def test_extract_workflow_metadata_missing_request(self):
        """Should raise ValueError if feature_request missing."""
        session_data = {
            'workflow_id': 'workflow-123',
            'agents': [],
        }

        with pytest.raises(ValueError, match='feature_request not found'):
            extract_workflow_metadata(session_data)

    def test_extract_workflow_metadata_empty_workflow_id(self):
        """Should raise ValueError if workflow_id is empty string."""
        session_data = {
            'workflow_id': '',
            'feature_request': 'Add authentication',
            'agents': [],
        }

        with pytest.raises(ValueError, match='workflow_id cannot be empty'):
            extract_workflow_metadata(session_data)

    def test_extract_workflow_metadata_empty_request(self):
        """Should raise ValueError if feature_request is empty string."""
        session_data = {
            'workflow_id': 'workflow-123',
            'feature_request': '',
            'agents': [],
        }

        with pytest.raises(ValueError, match='feature_request cannot be empty'):
            extract_workflow_metadata(session_data)


class TestGitOperationsTrigger:
    """Test triggering git operations via auto_implement_git_integration module."""

    @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')
    def test_trigger_git_operations_success(self, mock_execute):
        """Should successfully trigger git operations and return result."""
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'branch': 'feature/auth',
            'pr_created': False,
        }

        result = trigger_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            consent={'git_enabled': True, 'push_enabled': False, 'pr_enabled': False}
        )

        assert result['success'] is True
        assert result['commit_sha'] == 'abc123'
        mock_execute.assert_called_once_with(
            workflow_id='workflow-123',
            request='Add authentication',
            push=False,
            create_pr=False
        )

    @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')
    def test_trigger_git_operations_with_push(self, mock_execute):
        """Should enable push when consent given."""
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'pushed': True,
        }

        result = trigger_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            consent={'git_enabled': True, 'push_enabled': True, 'pr_enabled': False}
        )

        assert result['success'] is True
        mock_execute.assert_called_once_with(
            workflow_id='workflow-123',
            request='Add authentication',
            push=True,
            create_pr=False
        )

    @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')
    def test_trigger_git_operations_with_pr(self, mock_execute):
        """Should enable PR creation when consent given."""
        mock_execute.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'pr_created': True,
            'pr_url': 'https://github.com/user/repo/pull/42',
        }

        result = trigger_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            consent={'git_enabled': True, 'push_enabled': True, 'pr_enabled': True}
        )

        assert result['success'] is True
        assert result['pr_created'] is True
        mock_execute.assert_called_once_with(
            workflow_id='workflow-123',
            request='Add authentication',
            push=True,
            create_pr=True
        )

    @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')
    def test_trigger_git_operations_failure(self, mock_execute):
        """Should handle git operation failures gracefully."""
        mock_execute.return_value = {
            'success': False,
            'error': 'Merge conflict detected',
            'manual_instructions': 'git pull origin main && git commit',
        }

        result = trigger_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            consent={'git_enabled': True, 'push_enabled': False, 'pr_enabled': False}
        )

        assert result['success'] is False
        assert 'error' in result
        assert 'manual_instructions' in result

    @patch('auto_git_workflow.auto_implement_git_integration.execute_step8_git_operations')
    def test_trigger_git_operations_exception(self, mock_execute):
        """Should catch exceptions and return error result."""
        mock_execute.side_effect = Exception('Network timeout')

        result = trigger_git_operations(
            workflow_id='workflow-123',
            request='Add authentication',
            consent={'git_enabled': True, 'push_enabled': False, 'pr_enabled': False}
        )

        assert result['success'] is False
        assert 'Network timeout' in result['error']


class TestRunHook:
    """Test main hook entry point - run_hook()."""

    @patch('auto_git_workflow.should_trigger_git_workflow')
    @patch('auto_git_workflow.check_git_workflow_consent')
    @patch('auto_git_workflow.get_session_file_path')
    @patch('auto_git_workflow.read_session_data')
    @patch('auto_git_workflow.extract_workflow_metadata')
    @patch('auto_git_workflow.trigger_git_operations')
    def test_run_hook_success_full_workflow(
        self,
        mock_trigger,
        mock_extract,
        mock_read,
        mock_get_path,
        mock_consent,
        mock_should_trigger,
        tmp_path,
    ):
        """Should successfully run full git workflow when all conditions met."""
        # Setup mocks
        mock_should_trigger.return_value = True
        mock_consent.return_value = {
            'git_enabled': True,
            'push_enabled': True,
            'pr_enabled': True,
            'all_enabled': True,
        }
        session_file = tmp_path / 'session.json'
        mock_get_path.return_value = session_file
        mock_read.return_value = {
            'workflow_id': 'workflow-123',
            'feature_request': 'Add auth',
        }
        mock_extract.return_value = {
            'workflow_id': 'workflow-123',
            'request': 'Add auth',
        }
        mock_trigger.return_value = {
            'success': True,
            'commit_sha': 'abc123',
            'pr_created': True,
            'pr_url': 'https://github.com/user/repo/pull/42',
        }

        # Run hook
        result = run_hook('quality-validator')

        # Assertions
        assert result['success'] is True
        assert result['commit_sha'] == 'abc123'
        assert result['pr_created'] is True
        mock_trigger.assert_called_once()

    @patch('auto_git_workflow.should_trigger_git_workflow')
    def test_run_hook_skip_wrong_agent(self, mock_should_trigger):
        """Should skip hook for agents other than quality-validator."""
        mock_should_trigger.return_value = False

        result = run_hook('doc-master')

        assert result['success'] is True
        assert result['skipped'] is True
        assert 'Not quality-validator' in result['reason']

    @patch('auto_git_workflow.should_trigger_git_workflow')
    @patch('auto_git_workflow.check_git_workflow_consent')
    def test_run_hook_skip_consent_not_given(self, mock_consent, mock_should_trigger):
        """Should skip hook when consent not given."""
        mock_should_trigger.return_value = True
        mock_consent.return_value = {
            'git_enabled': False,
            'push_enabled': False,
            'pr_enabled': False,
            'all_enabled': False,
        }

        result = run_hook('quality-validator')

        assert result['success'] is True
        assert result['skipped'] is True
        assert 'consent not given' in result['reason'].lower()

    @patch('auto_git_workflow.should_trigger_git_workflow')
    @patch('auto_git_workflow.check_git_workflow_consent')
    @patch('auto_git_workflow.get_session_file_path')
    @patch('auto_git_workflow.read_session_data')
    def test_run_hook_handles_session_read_error(
        self, mock_read, mock_get_path, mock_consent, mock_should_trigger, tmp_path
    ):
        """Should handle session read errors gracefully (non-blocking)."""
        mock_should_trigger.return_value = True
        mock_consent.return_value = {'git_enabled': True, 'all_enabled': False}
        mock_get_path.return_value = tmp_path / 'session.json'
        mock_read.side_effect = FileNotFoundError('Session file not found')

        result = run_hook('quality-validator')

        assert result['success'] is False
        assert 'Session file not found' in result['error']

    @patch('auto_git_workflow.should_trigger_git_workflow')
    @patch('auto_git_workflow.check_git_workflow_consent')
    @patch('auto_git_workflow.get_session_file_path')
    @patch('auto_git_workflow.read_session_data')
    @patch('auto_git_workflow.extract_workflow_metadata')
    @patch('auto_git_workflow.trigger_git_operations')
    def test_run_hook_handles_git_operation_error(
        self,
        mock_trigger,
        mock_extract,
        mock_read,
        mock_get_path,
        mock_consent,
        mock_should_trigger,
        tmp_path,
    ):
        """Should handle git operation errors and return manual instructions."""
        mock_should_trigger.return_value = True
        mock_consent.return_value = {'git_enabled': True, 'all_enabled': False}
        mock_get_path.return_value = tmp_path / 'session.json'
        mock_read.return_value = {'workflow_id': 'w-123', 'feature_request': 'Auth'}
        mock_extract.return_value = {'workflow_id': 'w-123', 'request': 'Auth'}
        mock_trigger.return_value = {
            'success': False,
            'error': 'Merge conflict',
            'manual_instructions': 'git pull && git commit',
        }

        result = run_hook('quality-validator')

        assert result['success'] is False
        assert 'Merge conflict' in result['error']
        assert 'manual_instructions' in result


class TestMainEntryPoint:
    """Test main() entry point - CLI interface."""

    @patch('auto_git_workflow.run_hook')
    def test_main_success(self, mock_run_hook):
        """Should invoke run_hook with agent name from environment."""
        mock_run_hook.return_value = {'success': True, 'commit_sha': 'abc123'}

        with patch.dict(os.environ, {'CLAUDE_AGENT_NAME': 'quality-validator'}):
            exit_code = main()

        assert exit_code == 0
        mock_run_hook.assert_called_once_with('quality-validator')

    @patch('auto_git_workflow.run_hook')
    def test_main_skip(self, mock_run_hook):
        """Should exit with 0 when hook skipped."""
        mock_run_hook.return_value = {'success': True, 'skipped': True}

        with patch.dict(os.environ, {'CLAUDE_AGENT_NAME': 'doc-master'}):
            exit_code = main()

        assert exit_code == 0

    @patch('auto_git_workflow.run_hook')
    def test_main_error(self, mock_run_hook):
        """Should exit with 1 on errors."""
        mock_run_hook.return_value = {'success': False, 'error': 'Git failed'}

        with patch.dict(os.environ, {'CLAUDE_AGENT_NAME': 'quality-validator'}):
            exit_code = main()

        assert exit_code == 1

    def test_main_no_agent_name_env(self):
        """Should exit with 1 when CLAUDE_AGENT_NAME not set."""
        with patch.dict(os.environ, {}, clear=True):
            exit_code = main()

        assert exit_code == 1

    @patch('auto_git_workflow.run_hook')
    def test_main_exception_handling(self, mock_run_hook):
        """Should catch exceptions and exit with 1."""
        mock_run_hook.side_effect = Exception('Unexpected error')

        with patch.dict(os.environ, {'CLAUDE_AGENT_NAME': 'quality-validator'}):
            exit_code = main()

        assert exit_code == 1


class TestSecurityValidation:
    """Test security-related validation (CWE coverage)."""

    def test_session_file_path_rejects_absolute_paths_outside_whitelist(self):
        """Should reject absolute paths outside allowed directories (CWE-22)."""
        dangerous_paths = [
            '/etc/passwd',
            '/root/.ssh/id_rsa',
            '/var/log/auth.log',
        ]

        for path in dangerous_paths:
            with patch.dict(os.environ, {'CLAUDE_SESSION': path}):
                with pytest.raises(ValueError, match='Path not in whitelist'):
                    get_session_file_path()

    def test_session_file_path_allows_tmp_directory(self):
        """Should allow paths in /tmp directory (test mode)."""
        with patch.dict(os.environ, {'CLAUDE_SESSION': '/tmp/session-123.json'}):
            path = get_session_file_path()
            assert str(path).startswith('/tmp')

    def test_session_file_path_allows_docs_sessions_directory(self):
        """Should allow paths in docs/sessions directory."""
        with patch.dict(os.environ, {
            'CLAUDE_SESSION': '/home/user/project/docs/sessions/session-123.json'
        }):
            # Should not raise (validated by security_utils)
            path = get_session_file_path()
            assert 'docs/sessions' in str(path)

    @patch('auto_git_workflow.security_utils.validate_path')
    def test_session_file_validation_uses_security_utils(self, mock_validate):
        """Should use security_utils.validate_path for session file validation."""
        mock_validate.return_value = Path('/tmp/session.json')

        with patch.dict(os.environ, {'CLAUDE_SESSION': '/tmp/session.json'}):
            get_session_file_path()

        # Should call security_utils.validate_path
        mock_validate.assert_called_once()

    def test_audit_logging_for_security_events(self, tmp_path):
        """Should log security events to audit log."""
        with patch('auto_git_workflow.security_utils.audit_log') as mock_audit:
            with patch.dict(os.environ, {'CLAUDE_SESSION': '../../../etc/passwd'}):
                with pytest.raises(ValueError):
                    get_session_file_path()

            # Should log path traversal attempt
            mock_audit.assert_called()
            call_args = mock_audit.call_args[0]
            assert 'path_traversal_attempt' in call_args or 'security_validation_failed' in call_args
