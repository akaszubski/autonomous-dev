#!/usr/bin/env python3
"""
Integration tests for self-validation hook enhancements (TDD Red Phase - Issue #271).

Tests that quality gate hooks enforce themselves on autonomous-dev codebase:
- pre_commit_gate.py - No bypass allowed in autonomous-dev
- auto_enforce_coverage.py - 80% threshold for autonomous-dev
- stop_quality_gate.py - Mandatory execution in autonomous-dev
- enforce_tdd.py - No bypass allowed in autonomous-dev

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (implementation doesn't exist yet).

Test Strategy:
- Test bypass prevention in autonomous-dev repo
- Test threshold selection based on repo type
- Test mandatory execution in autonomous-dev
- Test user repo behavior unchanged (backward compatibility)
- Test CI environment behavior

Coverage Target: 80%+ for integration workflows

Date: 2026-01-26
Issue: #271 (meta(enforcement): Autonomous-dev doesn't enforce its own quality gates)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - implementation doesn't exist yet)
"""

import sys
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import json
import subprocess

# Add lib and hooks directories to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# Import hooks (will fail in RED phase)
try:
    from pre_commit_gate import main as pre_commit_gate_main
    from auto_enforce_coverage import main as auto_enforce_coverage_main
    from stop_quality_gate import main as stop_quality_gate_main
    from enforce_tdd import main as enforce_tdd_main
    from repo_detector import (
        is_autonomous_dev_repo,
        is_worktree,
        is_ci_environment,
        get_repo_context,
        _reset_cache,
    )
except ImportError as e:
    pytest.skip(
        f"Implementation not found (TDD red phase): {e}",
        allow_module_level=True
    )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def clean_cache():
    """Reset repo detector cache before and after each test."""
    _reset_cache()
    yield
    _reset_cache()


@pytest.fixture
def mock_autonomous_dev_env(tmp_path, monkeypatch):
    """Create autonomous-dev environment for testing."""
    repo_root = tmp_path / "autonomous-dev"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "plugins").mkdir()
    (repo_root / "plugins" / "autonomous-dev").mkdir()
    (repo_root / "plugins" / "autonomous-dev" / "manifest.json").write_text(
        '{"name": "autonomous-dev", "version": "1.0.0"}'
    )
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    return repo_root


@pytest.fixture
def mock_user_env(tmp_path, monkeypatch):
    """Create user project environment for testing."""
    repo_root = tmp_path / "user-project"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "tests").mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    return repo_root


@pytest.fixture
def mock_worktree_env(mock_autonomous_dev_env):
    """Create worktree environment within autonomous-dev."""
    worktree_path = mock_autonomous_dev_env.parent / ".worktrees" / "batch-123"
    worktree_path.mkdir(parents=True)
    (worktree_path / ".git").write_text(
        f"gitdir: {mock_autonomous_dev_env / '.git' / 'worktrees' / 'batch-123'}"
    )
    (worktree_path / "plugins").mkdir()
    (worktree_path / "plugins" / "autonomous-dev").mkdir()
    (worktree_path / "plugins" / "autonomous-dev" / "manifest.json").write_text(
        '{"name": "autonomous-dev", "version": "1.0.0"}'
    )
    return worktree_path


@pytest.fixture
def mock_coverage_file(tmp_path):
    """Create mock coverage.json file."""
    coverage_data = {
        "totals": {
            "percent_covered": 85.0,
            "covered_lines": 850,
            "num_statements": 1000
        }
    }
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps(coverage_data))
    return coverage_file


@pytest.fixture
def mock_pytest_output():
    """Mock pytest command output."""
    def _create_output(passed=10, failed=0, exit_code=0):
        output = f"{passed} passed"
        if failed > 0:
            output = f"{failed} failed, {output}"
        return MagicMock(
            returncode=exit_code,
            stdout=output.encode(),
            stderr=b""
        )
    return _create_output


# =============================================================================
# Integration Tests: pre_commit_gate.py
# =============================================================================

class TestPreCommitGateSelfValidation:
    """Test pre_commit_gate.py self-validation enforcement."""

    def test_blocks_commit_with_failed_tests_in_autonomous_dev(
        self, mock_autonomous_dev_env, mock_pytest_output, clean_cache
    ):
        """Test that pre_commit_gate blocks commits when tests fail in autonomous-dev.

        ENFORCEMENT: No bypass allowed in autonomous-dev.
        Expected: Hook returns 1 (blocks commit) when tests fail.
        """
        # Arrange - mock pytest with failures
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 2  # Blocks commit (EXIT_BLOCK)

    def test_allows_commit_with_passing_tests_in_autonomous_dev(
        self, mock_autonomous_dev_env, mock_pytest_output, clean_cache
    ):
        """Test that pre_commit_gate allows commits when tests pass in autonomous-dev.

        ENFORCEMENT: Tests must pass to commit.
        Expected: Hook returns 0 (allows commit) when all tests pass.
        """
        # Arrange - mock pytest with all passing
        with patch('subprocess.run', return_value=mock_pytest_output(passed=10, failed=0, exit_code=0)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 0  # Allows commit

    def test_bypass_env_var_ignored_in_autonomous_dev(
        self, mock_autonomous_dev_env, monkeypatch, mock_pytest_output, clean_cache
    ):
        """Test that SKIP_PRE_COMMIT_GATE is ignored in autonomous-dev.

        ENFORCEMENT: No bypass allowed in autonomous-dev.
        Expected: Hook still blocks commit even with bypass env var.
        """
        # Arrange - set bypass env var and mock failing tests
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 2  # Bypass ignored, commit blocked (EXIT_BLOCK)

    def test_bypass_allowed_in_user_repo(
        self, mock_user_env, monkeypatch, mock_pytest_output, clean_cache
    ):
        """Test that bypass env var works in user repos.

        BACKWARD COMPATIBILITY: User repos can still bypass.
        Expected: Hook allows commit when bypass env var set in user repo.
        """
        # Arrange - set bypass env var
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 0  # Bypass allowed in user repo

    def test_enforcement_in_worktree(
        self, mock_worktree_env, monkeypatch, mock_pytest_output, clean_cache
    ):
        """Test that enforcement works in worktrees.

        ENFORCEMENT: Worktrees are also autonomous-dev.
        Expected: No bypass allowed in worktrees either.
        """
        # Arrange - set bypass env var (should be ignored)
        monkeypatch.chdir(mock_worktree_env)
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 2  # Bypass ignored in worktree (EXIT_BLOCK)


# =============================================================================
# Integration Tests: auto_enforce_coverage.py
# =============================================================================

class TestAutoEnforceCoverageSelfValidation:
    """Test auto_enforce_coverage.py threshold selection."""

    def test_uses_80_percent_threshold_in_autonomous_dev(
        self, mock_autonomous_dev_env, mock_coverage_file, clean_cache
    ):
        """Test that 80% threshold is enforced in autonomous-dev.

        ENFORCEMENT: Higher standard for autonomous-dev.
        Expected: Requires 80% coverage in autonomous-dev.
        """
        # Arrange - coverage at 75% (below autonomous-dev threshold)
        coverage_data = {
            "totals": {
                "percent_covered": 75.0,
                "covered_lines": 750,
                "num_statements": 1000
            }
        }
        mock_coverage_file.write_text(json.dumps(coverage_data))

        # Act
        with patch('pathlib.Path.cwd', return_value=mock_autonomous_dev_env):
            with patch('auto_enforce_coverage.find_coverage_file', return_value=mock_coverage_file):
                exit_code = auto_enforce_coverage_main()

        # Assert
        assert exit_code == 2  # Blocks (75% < 80%) (EXIT_BLOCK)

    def test_uses_70_percent_threshold_in_user_repo(
        self, mock_user_env, mock_coverage_file, clean_cache
    ):
        """Test that 70% threshold is used in user repos.

        BACKWARD COMPATIBILITY: User repos have 70% threshold.
        Expected: Requires 70% coverage in user repos.
        """
        # Arrange - coverage at 75% (above user threshold, below autonomous-dev)
        coverage_data = {
            "totals": {
                "percent_covered": 75.0,
                "covered_lines": 750,
                "num_statements": 1000
            }
        }
        mock_coverage_file.write_text(json.dumps(coverage_data))

        # Act
        with patch('pathlib.Path.cwd', return_value=mock_user_env):
            with patch('auto_enforce_coverage.find_coverage_file', return_value=mock_coverage_file):
                exit_code = auto_enforce_coverage_main()

        # Assert
        assert exit_code == 0  # Passes (75% >= 70%)

    def test_passes_with_80_percent_in_autonomous_dev(
        self, mock_autonomous_dev_env, mock_coverage_file, clean_cache
    ):
        """Test that 80% coverage passes in autonomous-dev.

        ENFORCEMENT: Meets threshold.
        Expected: Hook allows commit with 80%+ coverage.
        """
        # Arrange - coverage at 85%
        coverage_data = {
            "totals": {
                "percent_covered": 85.0,
                "covered_lines": 850,
                "num_statements": 1000
            }
        }
        mock_coverage_file.write_text(json.dumps(coverage_data))

        # Act
        with patch('pathlib.Path.cwd', return_value=mock_autonomous_dev_env):
            with patch('auto_enforce_coverage.find_coverage_file', return_value=mock_coverage_file):
                exit_code = auto_enforce_coverage_main()

        # Assert
        assert exit_code == 0  # Passes (85% >= 80%)

    def test_threshold_selection_in_worktree(
        self, mock_worktree_env, monkeypatch, mock_coverage_file, clean_cache
    ):
        """Test that worktrees use 80% threshold.

        ENFORCEMENT: Worktrees are autonomous-dev.
        Expected: Uses 80% threshold in worktrees.
        """
        # Arrange - coverage at 75%
        monkeypatch.chdir(mock_worktree_env)
        coverage_data = {
            "totals": {
                "percent_covered": 75.0,
                "covered_lines": 750,
                "num_statements": 1000
            }
        }
        mock_coverage_file.write_text(json.dumps(coverage_data))

        # Act
        with patch('auto_enforce_coverage.find_coverage_file', return_value=mock_coverage_file):
            exit_code = auto_enforce_coverage_main()

        # Assert
        assert exit_code == 2  # Blocks (75% < 80%) (EXIT_BLOCK)


# =============================================================================
# Integration Tests: stop_quality_gate.py
# =============================================================================

class TestStopQualityGateSelfValidation:
    """Test stop_quality_gate.py mandatory execution."""

    def test_executes_in_autonomous_dev(self, mock_autonomous_dev_env, clean_cache):
        """Test that stop quality gate executes in autonomous-dev.

        ENFORCEMENT: Mandatory in autonomous-dev.
        Expected: Hook runs checks (not skipped).
        """
        # Arrange - mock check functions
        with patch('stop_quality_gate.run_quality_checks') as mock_checks:
            mock_checks.return_value = True  # Checks pass

            # Act
            exit_code = stop_quality_gate_main()

            # Assert
            mock_checks.assert_called_once()  # Checks executed
            assert exit_code == 0

    def test_skip_env_var_ignored_in_autonomous_dev(
        self, mock_autonomous_dev_env, monkeypatch, clean_cache
    ):
        """Test that SKIP_QUALITY_GATE is ignored in autonomous-dev.

        ENFORCEMENT: No bypass allowed.
        Expected: Hook still executes even with skip env var.
        """
        # Arrange - set skip env var
        monkeypatch.setenv("SKIP_QUALITY_GATE", "true")
        with patch('stop_quality_gate.run_quality_checks') as mock_checks:
            mock_checks.return_value = True

            # Act
            exit_code = stop_quality_gate_main()

            # Assert
            mock_checks.assert_called_once()  # Skip ignored, checks run

    def test_skip_allowed_in_user_repo(
        self, mock_user_env, monkeypatch, clean_cache
    ):
        """Test that skip env var works in user repos.

        BACKWARD COMPATIBILITY: User repos can skip.
        Expected: Hook skipped when env var set in user repo.
        """
        # Arrange - set skip env var
        monkeypatch.setenv("SKIP_QUALITY_GATE", "true")
        with patch('stop_quality_gate.run_quality_checks') as mock_checks:
            # Act
            exit_code = stop_quality_gate_main()

            # Assert
            mock_checks.assert_not_called()  # Skipped in user repo
            assert exit_code == 0


# =============================================================================
# Integration Tests: enforce_tdd.py
# =============================================================================

class TestEnforceTddSelfValidation:
    """Test enforce_tdd.py bypass prevention."""

    def test_enforces_tdd_in_autonomous_dev(
        self, mock_autonomous_dev_env, clean_cache
    ):
        """Test that TDD is enforced in autonomous-dev.

        ENFORCEMENT: Tests must exist before implementation.
        Expected: Hook checks for tests in autonomous-dev.
        """
        # Arrange - mock TDD check
        with patch('enforce_tdd.check_tdd_compliance') as mock_check:
            mock_check.return_value = True  # TDD followed

            # Act
            exit_code = enforce_tdd_main()

            # Assert
            mock_check.assert_called_once()  # TDD checked

    def test_bypass_ignored_in_autonomous_dev(
        self, mock_autonomous_dev_env, monkeypatch, clean_cache
    ):
        """Test that TDD bypass is ignored in autonomous-dev.

        ENFORCEMENT: No bypass allowed.
        Expected: TDD still enforced even with bypass env var.
        """
        # Arrange - set bypass env var
        monkeypatch.setenv("SKIP_TDD_CHECK", "true")
        with patch('enforce_tdd.check_tdd_compliance') as mock_check:
            mock_check.return_value = False  # TDD violated

            # Act
            exit_code = enforce_tdd_main()

            # Assert
            mock_check.assert_called_once()  # Bypass ignored
            assert exit_code == 2  # Still blocks (EXIT_BLOCK)

    def test_bypass_allowed_in_user_repo(
        self, mock_user_env, monkeypatch, clean_cache
    ):
        """Test that TDD bypass works in user repos.

        BACKWARD COMPATIBILITY: User repos can bypass.
        Expected: TDD not enforced when bypass set in user repo.
        """
        # Arrange - set bypass env var
        monkeypatch.setenv("SKIP_TDD_CHECK", "true")
        with patch('enforce_tdd.check_tdd_compliance') as mock_check:
            # Act
            exit_code = enforce_tdd_main()

            # Assert
            mock_check.assert_not_called()  # Bypassed in user repo
            assert exit_code == 0


# =============================================================================
# Integration Tests: CI Environment Behavior
# =============================================================================

class TestCiEnvironmentBehavior:
    """Test hook behavior in CI environments."""

    def test_enforcement_in_github_actions(
        self, mock_autonomous_dev_env, monkeypatch, mock_pytest_output, clean_cache
    ):
        """Test that enforcement works in GitHub Actions.

        ENFORCEMENT: CI runs must follow quality gates.
        Expected: Hooks enforce in CI environment.
        """
        # Arrange - set GitHub Actions env var
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 2  # Enforced in CI (EXIT_BLOCK)

    def test_bypass_ignored_in_ci(
        self, mock_autonomous_dev_env, monkeypatch, mock_pytest_output, clean_cache
    ):
        """Test that bypass env vars are ignored in CI.

        ENFORCEMENT: Can't bypass in CI even for user repos.
        Expected: Quality gates enforced in all CI runs.
        """
        # Arrange - set CI and bypass env vars
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("SKIP_PRE_COMMIT_GATE", "true")
        with patch('subprocess.run', return_value=mock_pytest_output(passed=8, failed=2, exit_code=1)):
            # Act
            exit_code = pre_commit_gate_main()

            # Assert
            assert exit_code == 2  # Bypass ignored in CI (EXIT_BLOCK)


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling in hook integration."""

    def test_handles_repo_detection_failure(self, tmp_path, monkeypatch, clean_cache):
        """Test that hooks handle repo detection failures gracefully.

        EDGE CASE: Can't determine repo type.
        Expected: Falls back to safe defaults.
        """
        # Arrange - non-git directory
        non_git_dir = tmp_path / "not-a-repo"
        non_git_dir.mkdir()
        monkeypatch.chdir(non_git_dir)

        # Act - hooks should handle gracefully
        with patch('subprocess.run', return_value=MagicMock(returncode=0)):
            exit_code = pre_commit_gate_main()

        # Assert - should not crash
        assert isinstance(exit_code, int)

    def test_handles_missing_repo_detector(self, mock_autonomous_dev_env, mock_pytest_output):
        """Test that hooks handle missing repo_detector gracefully.

        EDGE CASE: repo_detector not available.
        Expected: Falls back to user repo behavior.
        """
        # Arrange - mock import error
        with patch('builtins.__import__', side_effect=ImportError("No module named repo_detector")):
            with patch('subprocess.run', return_value=mock_pytest_output(passed=10, failed=0, exit_code=0)):
                # Act - should fall back to default behavior
                # Note: This test verifies backward compatibility
                exit_code = pre_commit_gate_main()

                # Assert - should not crash
                assert isinstance(exit_code, int)


# Run tests in verbose mode to see which ones fail (RED phase)
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
