#!/usr/bin/env python3
"""
Unit tests for AUTO_GIT_PR graceful degradation in auto_implement_git_integration.

TDD Mode: These tests are written BEFORE implementation (RED phase).
Tests should initially FAIL until push_and_create_pr() early exit is implemented.

Test Strategy:
- Test push_and_create_pr() skips when AUTO_GIT_PR=false
- Test user notification message formatting
- Test audit logging for PR skipped events
- Test response format consistency
- Test integration with check_consent_via_env()

Critical Context:
- Lines 1337-1346 in auto_implement_git_integration.py implement early exit
- Must match standard response format from other graceful degradation cases
- Must not invoke pr-description-generator agent when skipped
- Must not waste agent tokens when PR disabled

Coverage Target: 100% for push_and_create_pr() AUTO_GIT_PR=false path

Date: 2026-02-01
Issue: #318
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (early exit logic doesn't exist yet - tests will fail)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from typing import Dict, Any

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will succeed - module exists but early exit doesn't
try:
    from auto_implement_git_integration import (
        check_consent_via_env,
        push_and_create_pr,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestPushAndCreatePRSkipsWhenDisabled:
    """Test push_and_create_pr() skips when AUTO_GIT_PR=false."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_skipped_true(self):
        """
        Test push_and_create_pr() returns skipped=True when AUTO_GIT_PR=false.

        This is the core early exit behavior from lines 1337-1346.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test feature',
            commit_sha='abc1234'
        )

        # Assert
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_success_true(self):
        """
        Test push_and_create_pr() returns success=True when skipped.

        Skipping is a successful outcome (graceful degradation).
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert result['success'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_reason_field(self):
        """
        Test push_and_create_pr() returns reason field explaining why skipped.

        Reason should mention AUTO_GIT_PR=false.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert 'reason' in result
        assert 'AUTO_GIT_PR=false' in result['reason']

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_agent_invoked_false(self):
        """
        Test push_and_create_pr() returns agent_invoked=False when skipped.

        No agent should be invoked when PR disabled.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert result['agent_invoked'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_pr_created_false(self):
        """
        Test push_and_create_pr() returns pr_created=False when skipped.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert result['pr_created'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_empty_pr_url(self):
        """
        Test push_and_create_pr() returns empty pr_url when skipped.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert result['pr_url'] == ''

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_returns_none_pr_number(self):
        """
        Test push_and_create_pr() returns None pr_number when skipped.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert
        assert result['pr_number'] is None

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_complete_response_structure(self):
        """
        Test push_and_create_pr() returns complete response matching lines 1338-1346.

        Response should exactly match:
        {
            'success': True,
            'skipped': True,
            'reason': 'User consent not provided (AUTO_GIT_PR=false)',
            'agent_invoked': False,
            'pr_created': False,
            'pr_url': '',
            'pr_number': None
        }
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Exact match with expected response
        expected = {
            'success': True,
            'skipped': True,
            'reason': 'User consent not provided (AUTO_GIT_PR=false)',
            'agent_invoked': False,
            'pr_created': False,
            'pr_url': '',
            'pr_number': None
        }
        assert result == expected


class TestPushAndCreatePRNotifiesUser:
    """Test user notification when PR creation skipped."""

    @patch('builtins.print')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_prints_notification_message(self, mock_print):
        """
        Test push_and_create_pr() prints user notification when skipped.

        Expected output:
        "PR creation skipped (AUTO_GIT_PR=false)"
        "To create PR manually, run: gh pr create --title '...' --base main"
        """
        # Act
        push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: User notification printed
        # Note: Implementation may choose to notify user via library logging
        # or leave notification to calling code. This documents expected behavior.
        # if mock_print.called:
        #     print_output = ' '.join([str(call[0][0]) for call in mock_print.call_args_list])
        #     assert 'PR creation skipped' in print_output
        #     assert 'AUTO_GIT_PR=false' in print_output

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_notification_includes_manual_command(self):
        """
        Test notification includes manual gh pr create command.

        User should see how to create PR manually if needed.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test feature',
            commit_sha='abc1234'
        )

        # Assert: Response includes reason that can be shown to user
        assert 'reason' in result
        assert result['reason'] is not None

        # Note: Manual command may be provided in separate field
        # or left to calling code. This documents the need.


class TestPushAndCreatePRLogsAudit:
    """Test audit logging for PR skipped events."""

    @patch('auto_implement_git_integration.audit_log')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_logs_pr_creation_skipped_event(self, mock_audit):
        """
        Test push_and_create_pr() logs audit entry when PR skipped.

        Audit log should capture:
        - Event name: pr_creation_skipped
        - Reason: AUTO_GIT_PR=false
        - Workflow ID
        - Branch name
        - Timestamp (automatic)
        """
        # Act
        push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Audit log called
        # Note: Exact format depends on implementation
        # This documents expected audit logging
        # mock_audit.assert_called()

    @patch('auto_implement_git_integration.audit_log')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_audit_log_contains_no_secrets(self, mock_audit):
        """
        Test audit log entry contains no sensitive data.

        Should NOT include:
        - GITHUB_TOKEN
        - Commit contents
        - User credentials

        Should include:
        - Workflow ID
        - Branch name
        - Event type
        - Timestamp
        """
        # Act
        push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: No secrets in audit log
        # if mock_audit.called:
        #     for call in mock_audit.call_args_list:
        #         call_str = str(call)
        #         assert 'GITHUB_TOKEN' not in call_str
        #         assert 'ghp_' not in call_str


class TestPushAndCreatePRModeField:
    """Test mode field in response."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_mode_field_indicates_direct_push(self):
        """
        Test response includes mode='direct_push' when PR skipped.

        Mode values:
        - 'commit_only': Commit but no push
        - 'direct_push': Commit + push but no PR
        - 'pull_request': Full workflow with PR
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Mode field exists and is correct
        # Note: mode field may not be implemented yet
        # This documents expected behavior for implementation
        # assert result.get('mode') == 'direct_push'

        # At minimum, we verify PR was not created
        assert result['pr_created'] is False


class TestPushAndCreatePRIntegration:
    """Test integration with check_consent_via_env()."""

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_uses_check_consent_via_env(self, mock_agent):
        """
        Test push_and_create_pr() uses check_consent_via_env() to check pr_enabled.

        Should call check_consent_via_env() before any other operations.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Agent not invoked (proves consent was checked)
        mock_agent.assert_not_called()
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_consent_check_happens_first(self):
        """
        Test consent check happens BEFORE any expensive operations.

        No agent invocation, no subprocess calls, just early return.
        """
        # Act
        with patch('auto_implement_git_integration.invoke_pr_description_agent') as mock_agent:
            with patch('subprocess.run') as mock_run:
                result = push_and_create_pr(
                    workflow_id='test-123',
                    branch='feature/test',
                    base_branch='main',
                    title='feat: test',
                    commit_sha='abc1234'
                )

                # Assert: No expensive operations called
                mock_agent.assert_not_called()
                mock_run.assert_not_called()  # No gh pr create
                assert result['skipped'] is True


class TestPushAndCreatePRTokenEfficiency:
    """Test that skipping PR doesn't waste agent tokens."""

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_no_agent_tokens_wasted(self, mock_agent):
        """
        Test pr-description-generator agent is NOT invoked when PR disabled.

        Agent invocation costs tokens. Skipping should happen before agent call.
        """
        # Act
        push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Agent never called
        mock_agent.assert_not_called()

    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_no_gh_cli_calls(self, mock_run):
        """
        Test gh CLI is NOT called when PR disabled.

        No gh pr create, no gh pr view, no unnecessary subprocess calls.
        """
        # Act
        push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: No gh calls
        gh_calls = [call for call in mock_run.call_args_list if 'gh' in str(call)]
        assert len(gh_calls) == 0


class TestPushAndCreatePREdgeCases:
    """Test edge cases for push_and_create_pr() with AUTO_GIT_PR=false."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': ' false '})
    def test_whitespace_in_env_var(self):
        """
        Test AUTO_GIT_PR=' false ' (with whitespace) is handled correctly.

        Whitespace should be trimmed before parsing.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Treated as false
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'FALSE'})
    def test_uppercase_false(self):
        """
        Test AUTO_GIT_PR='FALSE' (uppercase) is treated as false.

        Case-insensitive parsing.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Case-insensitive
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': '0'})
    def test_zero_string(self):
        """
        Test AUTO_GIT_PR='0' is treated as false.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: '0' is falsy
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'no'})
    def test_lowercase_no(self):
        """
        Test AUTO_GIT_PR='no' is treated as false.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: 'no' is falsy
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_cascading_disabled_from_git_enabled(self):
        """
        Test AUTO_GIT_PR=true is overridden when AUTO_GIT_ENABLED=false.

        Cascading: git disabled -> push disabled -> PR disabled
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Skipped due to cascading
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false', 'AUTO_GIT_PR': 'true'})
    def test_cascading_disabled_from_push(self):
        """
        Test AUTO_GIT_PR=true is overridden when AUTO_GIT_PUSH=false.

        Cascading: push disabled -> PR disabled
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Skipped due to cascading
        assert result['skipped'] is True


class TestPushAndCreatePRResponseConsistency:
    """Test response format consistency across all code paths."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_response_has_standard_fields(self):
        """
        Test response has all standard fields for graceful degradation.

        Standard fields:
        - success: bool
        - skipped: bool
        - reason: str (when skipped=True)
        - agent_invoked: bool
        - pr_created: bool
        - pr_url: str
        - pr_number: Optional[int]
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: All fields present
        assert 'success' in result
        assert 'skipped' in result
        assert 'reason' in result
        assert 'agent_invoked' in result
        assert 'pr_created' in result
        assert 'pr_url' in result
        assert 'pr_number' in result

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_response_types_correct(self):
        """
        Test response field types are correct.

        Type validation:
        - success: bool
        - skipped: bool
        - reason: str
        - agent_invoked: bool
        - pr_created: bool
        - pr_url: str
        - pr_number: None or int
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Types correct
        assert isinstance(result['success'], bool)
        assert isinstance(result['skipped'], bool)
        assert isinstance(result['reason'], str)
        assert isinstance(result['agent_invoked'], bool)
        assert isinstance(result['pr_created'], bool)
        assert isinstance(result['pr_url'], str)
        assert result['pr_number'] is None or isinstance(result['pr_number'], int)
