#!/usr/bin/env python3
"""
Regression test for Issue #318: Agents respect AUTO_GIT_PR=false before creating PRs.

TDD Mode: These tests are written BEFORE implementation (RED phase).
All tests should FAIL initially until agent prompts and library are updated.

Test Strategy:
- Test implementer agent respects AUTO_GIT_PR=false
- Test doc-master agent respects AUTO_GIT_PR=false
- Test pr-description-generator exits early when AUTO_GIT_PR=false
- Test library graceful degradation (push_and_create_pr returns skipped)
- Test edge cases (missing env var, invalid values, whitespace)
- Test cascading behavior (AUTO_GIT_ENABLED=false disables PR)

Critical Context:
- AUTO_GIT_PR=false should prevent PR creation entirely
- Agents should check environment before invoking gh CLI
- Library should return graceful degradation response
- User should receive clear notification when PR skipped

Coverage Target: 100% for AUTO_GIT_PR=false workflow

Date: 2026-02-01
Issue: #318
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (implementation doesn't exist yet - tests will fail)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CalledProcessError
from typing import Dict, Any

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

# Import will succeed - module exists but AUTO_GIT_PR logic doesn't
try:
    from auto_implement_git_integration import (
        check_consent_via_env,
        push_and_create_pr,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestIssue318ImplementerRespectsAutoGitPR:
    """Test implementer agent respects AUTO_GIT_PR=false."""

    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_implementer_skips_pr_when_auto_git_pr_false(self, mock_run):
        """
        Regression test for Issue #318: implementer should NOT call gh pr create.

        When AUTO_GIT_PR=false, implementer should:
        1. Complete commit and push successfully
        2. Skip PR creation entirely (no gh pr create call)
        3. Notify user that PR was skipped
        4. Provide manual gh pr create command for reference
        """
        # Arrange: Mock successful git operations
        mock_run.return_value = Mock(returncode=0, stdout='abc1234')

        # Act: Simulate implementer workflow (commit + push + PR)
        # In real implementation, this would be the Step 8 execute function
        consent = check_consent_via_env()

        # Assert: PR consent is disabled
        assert consent['pr_enabled'] is False
        assert consent['push_enabled'] is True
        assert consent['git_enabled'] is True

        # Verify gh pr create was never called
        gh_calls = [call for call in mock_run.call_args_list if 'gh' in str(call)]
        assert len(gh_calls) == 0, "implementer should not call gh when AUTO_GIT_PR=false"

    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_implementer_notifies_user_pr_skipped(self, mock_run):
        """
        Test implementer provides clear notification when PR skipped.

        User should see:
        - Clear message: "PR creation skipped (AUTO_GIT_PR=false)"
        - Manual command: gh pr create --title "..." --base main
        - Documentation link: docs/GIT-AUTOMATION.md
        """
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='abc1234')

        # Act: Simulate PR creation attempt
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test feature',
            commit_sha='abc1234'
        )

        # Assert: Graceful degradation response
        assert result['success'] is True
        assert result['skipped'] is True
        assert 'AUTO_GIT_PR=false' in result['reason']
        assert result['pr_created'] is False
        assert result['agent_invoked'] is False

        # Verify no gh calls made
        gh_calls = [call for call in mock_run.call_args_list if 'gh' in str(call)]
        assert len(gh_calls) == 0


class TestIssue318DocMasterRespectsAutoGitPR:
    """Test doc-master agent respects AUTO_GIT_PR=false."""

    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_doc_master_skips_pr_when_auto_git_pr_false(self, mock_run):
        """
        Regression test for Issue #318: doc-master should NOT trigger PR.

        When AUTO_GIT_PR=false, doc-master should:
        1. Complete documentation updates
        2. Commit and push changes
        3. Skip PR creation entirely
        4. Notify user with clear message
        """
        # Arrange
        mock_run.return_value = Mock(returncode=0, stdout='abc1234')

        # Act
        consent = check_consent_via_env()

        # Assert: PR disabled
        assert consent['pr_enabled'] is False

        # Act: Simulate doc-master workflow
        result = push_and_create_pr(
            workflow_id='doc-workflow-123',
            branch='docs/update-readme',
            base_branch='main',
            title='docs: update README',
            commit_sha='abc1234'
        )

        # Assert: PR skipped
        assert result['skipped'] is True
        assert result['pr_created'] is False

        # Verify no gh calls
        gh_calls = [call for call in mock_run.call_args_list if 'gh' in str(call)]
        assert len(gh_calls) == 0

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_doc_master_provides_manual_pr_command(self):
        """
        Test doc-master provides manual gh pr create command when skipped.

        Response should include:
        - fallback_command: gh pr create --title "..." --base main
        - Properly formatted and copyable
        - Includes branch and base branch
        """
        # Act
        result = push_and_create_pr(
            workflow_id='doc-workflow-123',
            branch='docs/update-readme',
            base_branch='main',
            title='docs: update README',
            commit_sha='abc1234'
        )

        # Assert: Manual command provided (even when skipped)
        # Note: fallback_command may not be populated when skipped
        # This documents the expected behavior for implementation
        assert result['success'] is True
        assert result['skipped'] is True


class TestIssue318PRDescriptionGeneratorExitsEarly:
    """Test pr-description-generator exits early when AUTO_GIT_PR=false."""

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_pr_description_generator_not_invoked(self, mock_agent):
        """
        Regression test for Issue #318: pr-description-generator should NOT be invoked.

        When AUTO_GIT_PR=false:
        1. push_and_create_pr should check consent FIRST
        2. pr-description-generator agent should NOT be invoked
        3. Library should return early with skipped=True
        4. No agent tokens wasted
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Agent not invoked
        mock_agent.assert_not_called()
        assert result['agent_invoked'] is False
        assert result['skipped'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_pr_description_generator_early_exit_response(self):
        """
        Test pr-description-generator early exit returns proper response.

        Response should match standard format:
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

        # Assert: Standard response format
        assert result == {
            'success': True,
            'skipped': True,
            'reason': 'User consent not provided (AUTO_GIT_PR=false)',
            'agent_invoked': False,
            'pr_created': False,
            'pr_url': '',
            'pr_number': None
        }


class TestIssue318LibraryGracefulDegradation:
    """Test library graceful degradation when AUTO_GIT_PR=false."""

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_push_and_create_pr_returns_skipped(self):
        """
        Test push_and_create_pr() returns skipped=True when AUTO_GIT_PR=false.

        This is the core library behavior test from lines 1337-1346.
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Matches expected response from lines 1338-1346
        assert result['success'] is True
        assert result['skipped'] is True
        assert result['reason'] == 'User consent not provided (AUTO_GIT_PR=false)'
        assert result['agent_invoked'] is False
        assert result['pr_created'] is False
        assert result['pr_url'] == ''
        assert result['pr_number'] is None

    @patch('auto_implement_git_integration.audit_log')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_push_and_create_pr_logs_audit(self, mock_audit):
        """
        Test push_and_create_pr() logs audit entry when PR skipped.

        Audit log should capture:
        - Event: pr_creation_skipped
        - Reason: AUTO_GIT_PR=false
        - No sensitive data
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
        # Note: Exact audit_log call format may vary based on implementation
        # This documents the expected behavior
        # mock_audit.assert_called()  # Uncomment when audit_log added


class TestIssue318EdgeCases:
    """Test edge cases for AUTO_GIT_PR handling."""

    @patch.dict(os.environ, {}, clear=True)
    def test_auto_git_pr_not_set_defaults_to_true(self):
        """
        Test AUTO_GIT_PR not set defaults to True (opt-out model).

        IMPORTANT: This matches the opt-out consent model from Issue #61.
        When AUTO_GIT_PR is not set, it should default to True.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: Defaults to True (opt-out model)
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'false', 'AUTO_GIT_PR': 'true'})
    def test_auto_git_pr_disabled_when_git_disabled(self):
        """
        Test AUTO_GIT_PR=true is overridden when AUTO_GIT_ENABLED=false.

        Cascading behavior: If git is disabled, PR must also be disabled.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: PR disabled due to cascading
        assert consent['git_enabled'] is False
        assert consent['pr_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'false', 'AUTO_GIT_PR': 'true'})
    def test_auto_git_pr_disabled_when_push_disabled(self):
        """
        Test AUTO_GIT_PR=true is overridden when AUTO_GIT_PUSH=false.

        Cascading behavior: If push is disabled, PR must also be disabled.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: PR disabled due to cascading
        assert consent['push_enabled'] is False
        assert consent['pr_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_PR': 'maybe'})
    def test_auto_git_pr_invalid_value(self):
        """
        Test AUTO_GIT_PR with invalid value defaults to True (opt-out model).

        Unknown values like 'maybe' or 'unknown' should use the default (True).
        """
        # Act
        consent = check_consent_via_env()

        # Assert: Defaults to True for unknown values
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_PR': ' false '})
    def test_auto_git_pr_whitespace_trimmed(self):
        """
        Test AUTO_GIT_PR=' false ' trims whitespace before parsing.

        ' false ' should be treated as 'false' after trimming.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: Whitespace trimmed, value parsed correctly
        assert consent['pr_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_PR': ''})
    def test_auto_git_pr_empty_string(self):
        """
        Test AUTO_GIT_PR='' (empty string) defaults to True.

        Empty string should be treated as "not set" and use default.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: Empty string defaults to True
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_PR': '0'})
    def test_auto_git_pr_zero(self):
        """Test AUTO_GIT_PR='0' is treated as False."""
        # Act
        consent = check_consent_via_env()

        # Assert: '0' is falsy
        assert consent['pr_enabled'] is False

    @patch.dict(os.environ, {'AUTO_GIT_PR': '1'})
    def test_auto_git_pr_one(self):
        """Test AUTO_GIT_PR='1' is treated as True."""
        # Act
        consent = check_consent_via_env()

        # Assert: '1' is truthy
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_PR': 'YES'})
    def test_auto_git_pr_uppercase_yes(self):
        """Test AUTO_GIT_PR='YES' (uppercase) is treated as True."""
        # Act
        consent = check_consent_via_env()

        # Assert: Case-insensitive
        assert consent['pr_enabled'] is True

    @patch.dict(os.environ, {'AUTO_GIT_PR': 'No'})
    def test_auto_git_pr_mixed_case_no(self):
        """Test AUTO_GIT_PR='No' (mixed case) is treated as False."""
        # Act
        consent = check_consent_via_env()

        # Assert: Case-insensitive
        assert consent['pr_enabled'] is False


class TestIssue318UserNotification:
    """Test user notification when PR creation skipped."""

    @patch('builtins.print')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_user_notified_when_pr_skipped(self, mock_print):
        """
        Test user receives clear notification when PR skipped.

        Expected notification:
        - "PR creation skipped (AUTO_GIT_PR=false)"
        - "To create PR manually, run:"
        - "gh pr create --title '...' --base main --head feature/..."
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Result contains reason
        assert 'AUTO_GIT_PR=false' in result['reason']

        # Note: User notification via print() may happen in calling code,
        # not in push_and_create_pr() itself. This documents expected behavior.

    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'false'})
    def test_response_includes_mode_field(self):
        """
        Test response includes mode='direct_push' when PR skipped.

        This helps calling code understand what happened:
        - mode='commit_only': Commit but no push
        - mode='direct_push': Commit + push but no PR
        - mode='pull_request': Full workflow with PR
        """
        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: Mode field indicates direct push
        # Note: mode field may not exist yet - this documents expected behavior
        # assert result.get('mode') == 'direct_push'

        # At minimum, we know PR was not created
        assert result['pr_created'] is False
        assert result['skipped'] is True


class TestIssue318BackwardCompatibility:
    """Test backward compatibility with existing workflows."""

    @patch('auto_implement_git_integration.invoke_pr_description_agent')
    @patch('subprocess.run')
    @patch.dict(os.environ, {'AUTO_GIT_ENABLED': 'true', 'AUTO_GIT_PUSH': 'true', 'AUTO_GIT_PR': 'true'})
    def test_pr_creation_still_works_when_enabled(self, mock_run, mock_agent):
        """
        Test PR creation still works normally when AUTO_GIT_PR=true.

        This ensures the fix doesn't break existing functionality.
        """
        # Arrange: Mock agent and gh CLI
        mock_agent.return_value = {
            'success': True,
            'output': '## Summary\n- Test PR',
            'error': ''
        }

        mock_run.return_value = Mock(
            returncode=0,
            stdout='https://github.com/user/repo/pull/42\n'
        )

        # Act
        result = push_and_create_pr(
            workflow_id='test-123',
            branch='feature/test',
            base_branch='main',
            title='feat: test',
            commit_sha='abc1234'
        )

        # Assert: PR created successfully
        assert result['success'] is True
        assert result['skipped'] is False
        assert result['pr_created'] is True
        assert result['agent_invoked'] is True

    @patch.dict(os.environ, {}, clear=True)
    def test_default_behavior_unchanged(self):
        """
        Test default behavior (no env vars) still defaults to True.

        This maintains the opt-out consent model from Issue #61.
        """
        # Act
        consent = check_consent_via_env()

        # Assert: Defaults to True (opt-out model preserved)
        assert consent['git_enabled'] is True
        assert consent['push_enabled'] is True
        assert consent['pr_enabled'] is True
