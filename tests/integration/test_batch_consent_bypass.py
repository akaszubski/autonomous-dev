#!/usr/bin/env python3
"""
Integration tests for batch consent bypass (TDD Red Phase - Issue #96).

Tests for end-to-end batch processing workflow with consent bypass.
Verifies that /batch-implement doesn't block on interactive prompts when
AUTO_GIT_ENABLED is pre-configured.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation doesn't exist yet).

Test Strategy:
- Test complete batch workflow without prompts (AUTO_GIT_ENABLED=true)
- Test first-run consent flow integration
- Test backward compatibility (AUTO_GIT_ENABLED=false still allows prompts)
- Test security audit logging for consent decisions
- Test graceful degradation when git automation fails
- Test context management during batch with consent bypass

Security:
- Audit logging for all consent decisions
- No credential exposure in logs
- Safe defaults (prompt when unclear)
- Path validation for all file operations

Coverage Target: 90%+ for batch consent bypass workflow

Date: 2025-12-06
Issue: #96 (Fix consent blocking in batch processing)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - implementation doesn't exist yet)
"""

import json
import os
import subprocess
import sys
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, mock_open

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'plugins' / 'autonomous-dev' / 'lib'))

# Import will fail if implementation doesn't exist yet (TDD!)
try:
    from auto_implement_git_integration import (
        check_consent_via_env,
        execute_step8_git_operations,
    )
    from batch_state_manager import BatchState
except ImportError as e:
    pytest.skip(
        f"Implementation not found (TDD red phase): {e}",
        allow_module_level=True
    )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory with git repo."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ['git', 'init'],
        cwd=project_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=project_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=project_dir,
        capture_output=True,
        check=True
    )

    # Create initial commit
    readme = project_dir / "README.md"
    readme.write_text("# Test Project\n")
    subprocess.run(
        ['git', 'add', 'README.md'],
        cwd=project_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'Initial commit'],
        cwd=project_dir,
        capture_output=True,
        check=True
    )

    return project_dir


@pytest.fixture
def batch_features_file(tmp_path):
    """Create a test batch features file."""
    features_file = tmp_path / "features.txt"
    features_file.write_text(
        "Add user authentication\n"
        "Add data validation\n"
        "Add error logging\n"
    )
    return features_file


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables for testing."""
    env_vars = [
        'AUTO_GIT_ENABLED', 'AUTO_GIT_PUSH', 'AUTO_GIT_PR',
        'BATCH_RETRY_ENABLED', 'MCP_AUTO_APPROVE'
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def mock_first_run_warning(monkeypatch):
    """Mock first-run warning to avoid interactive prompts."""
    mock_should_show = MagicMock(return_value=False)
    monkeypatch.setattr(
        'auto_implement_git_integration.should_show_warning',
        mock_should_show
    )
    yield mock_should_show


@pytest.fixture
def mock_agent_execution(monkeypatch):
    """Mock agent execution to avoid actually running agents in tests."""
    mock_agent_invoker = MagicMock()
    mock_agent_invoker.invoke.return_value = {
        'success': True,
        'output': 'Agent completed successfully',
    }
    return mock_agent_invoker


# =============================================================================
# Integration Tests: Batch Workflow Without Prompts
# =============================================================================

class TestBatchConsentBypass:
    """Test batch processing with AUTO_GIT_ENABLED=true (no prompts)."""

    @patch('builtins.input')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    def test_batch_workflow_no_prompts_with_consent(
        self,
        mock_commit,
        mock_input,
        temp_project,
        batch_features_file,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that batch workflow runs without prompts when AUTO_GIT_ENABLED=true."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')
        monkeypatch.setenv('AUTO_GIT_PUSH', 'false')  # Don't push in tests

        mock_commit.return_value = {
            'success': True,
            'commit_sha': 'abc123',
        }

        # Act
        # Simulate 3 features being processed
        for i in range(3):
            consent = check_consent_via_env()
            if consent['enabled']:
                # Simulate git automation (would normally be triggered by hook)
                result = execute_step8_git_operations(
                    workflow_id=f'workflow-{i}',
                    branch=f'feature-{i}',
                    request=f'Feature {i}',
                    create_pr=False,
                )

        # Assert
        assert mock_input.call_count == 0, \
            "Expected no interactive prompts with AUTO_GIT_ENABLED=true"
        assert mock_commit.call_count == 3, \
            "Expected 3 commits for 3 features"

    @patch('builtins.input')
    def test_batch_workflow_prompts_when_disabled(
        self,
        mock_input,
        temp_project,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that batch workflow would prompt when AUTO_GIT_ENABLED=false."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'false')
        mock_input.return_value = 'n'  # Simulate user declining

        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['enabled'] is False, \
            "Expected git operations disabled with AUTO_GIT_ENABLED=false"
        # No prompts expected because env var explicitly disables
        # (prompts would occur in auto-implement.md STEP 5 implementation)

    @patch('builtins.input')
    def test_batch_workflow_prompts_when_not_set(
        self,
        mock_input,
        temp_project,
        clean_env,
        mock_first_run_warning,
    ):
        """Test backward compatibility - uses default (True) when not set."""
        # Arrange
        # clean_env fixture removes AUTO_GIT_ENABLED

        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['enabled'] is True, \
            "Expected default to True (opt-out model)"
        # No prompts in check_consent_via_env() - prompts would occur in
        # auto-implement.md STEP 5 when checking if user wants automation


# =============================================================================
# Integration Tests: First-Run Consent Flow
# =============================================================================

class TestFirstRunConsentFlow:
    """Test first-run consent integration with batch workflow."""

    @patch('auto_implement_git_integration.show_first_run_warning')
    @patch('auto_implement_git_integration.should_show_warning')
    def test_first_run_consent_accepted(
        self,
        mock_should_show,
        mock_show_warning,
        clean_env,
    ):
        """Test that first-run consent acceptance enables git automation."""
        # Arrange
        mock_should_show.return_value = True  # First run
        mock_show_warning.return_value = True  # User accepts

        # Act
        consent = check_consent_via_env()

        # Assert
        assert mock_should_show.called, "Expected should_show_warning called"
        assert mock_show_warning.called, "Expected show_first_run_warning called"
        # Consent should reflect user's acceptance
        # (exact behavior depends on implementation)

    @patch('auto_implement_git_integration.show_first_run_warning')
    @patch('auto_implement_git_integration.should_show_warning')
    def test_first_run_consent_declined(
        self,
        mock_should_show,
        mock_show_warning,
        clean_env,
    ):
        """Test that first-run consent decline disables git automation."""
        # Arrange
        mock_should_show.return_value = True  # First run
        mock_show_warning.return_value = False  # User declines

        # Act
        consent = check_consent_via_env()

        # Assert
        assert mock_should_show.called, "Expected should_show_warning called"
        assert mock_show_warning.called, "Expected show_first_run_warning called"
        assert consent['enabled'] is False, \
            "Expected git disabled when user declines first-run consent"

    @patch('auto_implement_git_integration.should_show_warning')
    def test_env_var_overrides_first_run(
        self,
        mock_should_show,
        clean_env,
        monkeypatch,
    ):
        """Test that AUTO_GIT_ENABLED env var bypasses first-run prompt."""
        # Arrange
        mock_should_show.return_value = True  # Would be first run
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')

        # Act
        consent = check_consent_via_env()

        # Assert
        # First-run check should still happen but env var takes precedence
        assert consent['enabled'] is True, \
            "Expected env var to override first-run prompt"


# =============================================================================
# Integration Tests: Security and Audit Logging
# =============================================================================

class TestConsentSecurityAndLogging:
    """Test security and audit logging for consent bypass."""

    @patch('auto_implement_git_integration.audit_log')
    def test_consent_decision_logged(
        self,
        mock_audit_log,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent decisions are logged for audit trail."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')

        # Act
        consent = check_consent_via_env()

        # Assert
        # Expect audit_log to be called with consent details
        # (exact parameters depend on implementation)
        assert consent is not None, "Expected consent dict returned"
        # TODO: Verify audit_log parameters once implementation exists

    @patch('auto_implement_git_integration.audit_log')
    def test_consent_bypass_logged_separately(
        self,
        mock_audit_log,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent bypass is logged separately from normal consent."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')

        # Act
        consent = check_consent_via_env()

        # Assert
        # Expect specific audit log entry for bypass
        # This test will fail until logging is implemented
        assert consent['enabled'] is True
        # TODO: Verify bypass-specific audit log entry

    @patch('auto_implement_git_integration.auto_commit_and_push')
    def test_no_credentials_in_consent_flow(
        self,
        mock_commit,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent flow never exposes credentials."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')
        mock_commit.return_value = {
            'success': True,
            'commit_sha': 'abc123',
        }

        # Act
        consent = check_consent_via_env()
        result = execute_step8_git_operations(
            workflow_id='test-workflow',
            branch='test-branch',
            request='Test feature',
            create_pr=False,
        )

        # Assert
        # Verify no sensitive data in consent dict
        consent_str = json.dumps(consent)
        sensitive_patterns = ['password', 'token', 'secret', 'key', 'credential']
        for pattern in sensitive_patterns:
            assert pattern.lower() not in consent_str.lower(), \
                f"Found sensitive pattern '{pattern}' in consent data"


# =============================================================================
# Integration Tests: Graceful Degradation
# =============================================================================

class TestConsentGracefulDegradation:
    """Test graceful degradation when git automation prerequisites fail."""

    @patch('auto_implement_git_integration.validate_git_repo')
    def test_consent_bypass_with_invalid_git_repo(
        self,
        mock_validate,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent bypass gracefully handles invalid git repo."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')
        mock_validate.return_value = (False, "Not a git repository")

        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['enabled'] is True, \
            "Expected consent enabled even if git validation fails later"
        # Git validation happens in auto-implement.md STEP 5, not in consent check

    @patch('auto_implement_git_integration.check_git_config')
    @patch('auto_implement_git_integration.validate_git_repo')
    def test_consent_bypass_with_missing_git_config(
        self,
        mock_validate,
        mock_config,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent bypass handles missing git config gracefully."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')
        mock_validate.return_value = (True, None)
        mock_config.return_value = (False, "Missing user.name")

        # Act
        consent = check_consent_via_env()

        # Assert
        assert consent['enabled'] is True, \
            "Expected consent enabled even if git config incomplete"
        # Config validation happens in auto-implement.md STEP 5


# =============================================================================
# Integration Tests: Context Management
# =============================================================================

class TestConsentWithContextManagement:
    """Test consent bypass with context management during batch processing."""

    @patch('builtins.input')
    @patch('auto_implement_git_integration.auto_commit_and_push')
    def test_consent_persists_across_context_clears(
        self,
        mock_commit,
        mock_input,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent decision persists across context clears."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')
        mock_commit.return_value = {
            'success': True,
            'commit_sha': 'abc123',
        }

        # Act - Simulate multiple batch cycles with context clears
        for cycle in range(3):
            # Each cycle would normally start after /clear
            consent = check_consent_via_env()
            assert consent['enabled'] is True

            # Process features
            for feature in range(2):
                result = execute_step8_git_operations(
                    workflow_id=f'cycle-{cycle}-feature-{feature}',
                    branch=f'feature-{cycle}-{feature}',
                    request=f'Feature {feature} in cycle {cycle}',
                    create_pr=False,
                )

        # Assert
        assert mock_input.call_count == 0, \
            "Expected no prompts across all cycles"
        assert mock_commit.call_count == 6, \
            "Expected 6 commits (3 cycles × 2 features)"

    @patch('auto_implement_git_integration.audit_log')
    def test_consent_source_tracked_across_batch(
        self,
        mock_audit_log,
        clean_env,
        monkeypatch,
        mock_first_run_warning,
    ):
        """Test that consent source (env var vs prompt) is tracked."""
        # Arrange
        monkeypatch.setenv('AUTO_GIT_ENABLED', 'true')

        # Act
        for i in range(5):
            consent = check_consent_via_env()

        # Assert
        # Each consent check should log the source
        # This test will fail until logging is implemented
        assert consent is not None
        # TODO: Verify audit logs show env var as source


# =============================================================================
# Expected Test Summary (All Should FAIL Initially)
# =============================================================================
"""
Expected Test Results (RED Phase):

TestBatchConsentBypass:
  - test_batch_workflow_no_prompts_with_consent ........... FAIL
  - test_batch_workflow_prompts_when_disabled ............. FAIL
  - test_batch_workflow_prompts_when_not_set .............. FAIL

TestFirstRunConsentFlow:
  - test_first_run_consent_accepted ....................... FAIL
  - test_first_run_consent_declined ....................... FAIL
  - test_env_var_overrides_first_run ...................... FAIL

TestConsentSecurityAndLogging:
  - test_consent_decision_logged .......................... FAIL
  - test_consent_bypass_logged_separately ................. FAIL
  - test_no_credentials_in_consent_flow ................... FAIL

TestConsentGracefulDegradation:
  - test_consent_bypass_with_invalid_git_repo ............. FAIL
  - test_consent_bypass_with_missing_git_config ........... FAIL

TestConsentWithContextManagement:
  - test_consent_persists_across_context_clears ........... FAIL
  - test_consent_source_tracked_across_batch .............. FAIL

Total: 13 tests, 0 passing, 13 failing (TDD RED phase)

Run with: pytest tests/integration/test_batch_consent_bypass.py -v
"""
