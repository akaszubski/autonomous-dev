"""Unit tests for drain_revert.py module with mocked subprocess calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch, call

import pytest

# Add lib to path
_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import drain_revert


class TestDetectRegression:
    """Tests for detect_regression function."""
    
    def test_detects_increased_pytest_failures(self, tmp_path: Path):
        """Regression detected when more tests fail after than before."""
        before = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": ["test_a"]}
        after = {"test_count": 100, "coverage_pct": 79.0, "failing_tests": ["test_a", "test_b"]}
        
        assert drain_revert.detect_regression(before, after, tmp_path) is True
    
    def test_no_regression_when_failures_decrease(self, tmp_path: Path):
        """No regression when fewer tests fail after."""
        before = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": ["test_a", "test_b"]}
        after = {"test_count": 100, "coverage_pct": 81.0, "failing_tests": ["test_a"]}
        
        assert drain_revert.detect_regression(before, after, tmp_path) is False
    
    def test_no_regression_when_failures_unchanged(self, tmp_path: Path):
        """No regression when same tests fail."""
        before = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": ["test_a"]}
        after = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": ["test_a"]}
        
        assert drain_revert.detect_regression(before, after, tmp_path) is False
    
    def test_detects_precommit_failure(self, tmp_path: Path, monkeypatch):
        """Regression detected when pre-commit validation fails."""
        # Create a fake validation script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        validation_script = scripts_dir / "validate_structure.py"
        validation_script.touch()
        
        # Mock subprocess to return failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "validation failed"
        
        with patch("drain_revert.subprocess.run", return_value=mock_result) as mock_run:
            before = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": []}
            after = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": []}
            
            result = drain_revert.detect_regression(before, after, tmp_path)
            assert result is True
            
            # Verify subprocess was called with correct kwargs
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["cwd"] == str(tmp_path)
            assert "env" in call_kwargs
            assert call_kwargs["timeout"] == 30
            assert call_kwargs["check"] is False
            assert call_kwargs["capture_output"] is True
            assert call_kwargs["text"] is True
    
    def test_no_regression_on_precommit_timeout(self, tmp_path: Path):
        """No regression assumed if pre-commit check times out."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        validation_script = scripts_dir / "validate_structure.py"
        validation_script.touch()
        
        with patch("drain_revert.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            before = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": []}
            after = {"test_count": 100, "coverage_pct": 80.0, "failing_tests": []}
            
            result = drain_revert.detect_regression(before, after, tmp_path)
            assert result is False


class TestFindFixCommits:
    """Tests for find_fix_commits function."""
    
    def test_finds_commits_referencing_sha(self, tmp_path: Path):
        """Successfully finds commits that reference the drain SHA."""
        drain_sha = "a" * 40
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "b" * 40 + "\n" + "c" * 40
        
        with patch("drain_revert.subprocess.run", return_value=mock_result) as mock_run:
            env = {"PATH": "/usr/bin"}
            result = drain_revert.find_fix_commits(drain_sha, tmp_path, env)
            
            assert result == ["b" * 40, "c" * 40]
            
            # Verify subprocess kwargs
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["cwd"] == str(tmp_path)
            assert call_kwargs["env"] == env
            assert call_kwargs["timeout"] == 10
    
    def test_returns_empty_on_git_error(self, tmp_path: Path):
        """Returns empty list when git command fails."""
        drain_sha = "a" * 40
        mock_result = MagicMock()
        mock_result.returncode = 1
        
        with patch("drain_revert.subprocess.run", return_value=mock_result):
            result = drain_revert.find_fix_commits(drain_sha, tmp_path, {})
            assert result == []
    
    def test_rejects_invalid_sha(self, tmp_path: Path):
        """Raises ValueError for invalid SHA format."""
        with pytest.raises(ValueError, match="Invalid SHA format"):
            drain_revert.find_fix_commits("invalid--exec=evil", tmp_path, {})
    
    def test_filters_invalid_shas_from_output(self, tmp_path: Path):
        """Filters out invalid SHAs from git output."""
        drain_sha = "a" * 40
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "b" * 40 + "\ninvalid\n" + "c" * 40
        
        with patch("drain_revert.subprocess.run", return_value=mock_result):
            result = drain_revert.find_fix_commits(drain_sha, tmp_path, {})
            assert result == ["b" * 40, "c" * 40]


class TestRevertDrainCommit:
    """Tests for revert_drain_commit function."""
    
    def test_successful_revert(self, tmp_path: Path):
        """Successfully reverts a commit and returns revert SHA."""
        drain_sha = "a" * 40
        revert_sha = "b" * 40
        
        # Mock both git revert and git rev-parse
        revert_result = MagicMock()
        revert_result.returncode = 0
        
        revparse_result = MagicMock()
        revparse_result.returncode = 0
        revparse_result.stdout = revert_sha
        
        with patch("drain_revert.subprocess.run", side_effect=[revert_result, revparse_result]) as mock_run:
            env = {"PATH": "/usr/bin"}
            success, result = drain_revert.revert_drain_commit(drain_sha, tmp_path, env)
            
            assert success is True
            assert result == revert_sha
            
            # Verify both subprocess calls
            assert mock_run.call_count == 2
            
            # First call (git revert)
            first_call = mock_run.call_args_list[0][1]
            assert first_call["cwd"] == str(tmp_path)
            assert first_call["env"] == env
            assert first_call["timeout"] == 30
            
            # Second call (git rev-parse)
            second_call = mock_run.call_args_list[1][1]
            assert second_call["cwd"] == str(tmp_path)
            assert second_call["timeout"] == 5
    
    def test_revert_failure(self, tmp_path: Path):
        """Returns failure when git revert fails."""
        drain_sha = "a" * 40
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "merge conflict"
        
        with patch("drain_revert.subprocess.run", return_value=mock_result):
            success, error_msg = drain_revert.revert_drain_commit(drain_sha, tmp_path, {})
            
            assert success is False
            assert "merge conflict" in error_msg
    
    def test_cwe88_sha_validation_rejects_injection(self, tmp_path: Path):
        """CWE-88 test: Rejects SHA with embedded command injection attempt."""
        evil_sha = "aaaa--exec=evil"
        
        success, error_msg = drain_revert.revert_drain_commit(evil_sha, tmp_path, {})
        
        assert success is False
        assert "Invalid SHA format" in error_msg
    
    def test_accepts_valid_40_char_hex(self, tmp_path: Path):
        """Accepts valid 40-character hex SHA."""
        valid_sha = "0123456789abcdef" * 2 + "01234567"  # 40 chars
        mock_result = MagicMock()
        mock_result.returncode = 1  # Will fail at git, but should pass validation
        
        with patch("drain_revert.subprocess.run", return_value=mock_result):
            success, _ = drain_revert.revert_drain_commit(valid_sha, tmp_path, {})
            # We don't care about success here, just that it got past validation
            assert success is False  # Failed at git, not validation


class TestReopenIssuesWithLabel:
    """Tests for reopen_issues_with_label function."""
    
    def test_reopens_issues_successfully(self, tmp_path: Path):
        """Successfully reopens issues with label and comment."""
        issues = [123, 456]
        drain_sha = "a" * 40
        revert_sha = "b" * 40
        
        # Mock all gh commands to succeed
        success_result = MagicMock()
        success_result.returncode = 0
        
        with patch("drain_revert.subprocess.run", return_value=success_result) as mock_run:
            # Also need to mock ensure_drain_reverted_label_exists
            with patch("drain_revert.ensure_drain_reverted_label_exists", return_value=True):
                env = {"PATH": "/usr/bin"}
                count = drain_revert.reopen_issues_with_label(
                    issues, drain_sha, revert_sha, tmp_path, env
                )
                
                assert count == 2
                
                # Should have called: reopen, add-label, comment for each issue
                # Plus the label exists check
                assert mock_run.call_count >= 6
    
    def test_skips_invalid_issue_numbers(self, tmp_path: Path):
        """Skips non-integer and negative issue numbers."""
        issues = [123, -1, "invalid", 0, 456]
        drain_sha = "a" * 40
        revert_sha = "b" * 40
        
        success_result = MagicMock()
        success_result.returncode = 0
        
        with patch("drain_revert.subprocess.run", return_value=success_result):
            with patch("drain_revert.ensure_drain_reverted_label_exists", return_value=True):
                count = drain_revert.reopen_issues_with_label(
                    issues, drain_sha, revert_sha, tmp_path, {}
                )
                
                # Should only process 123 and 456
                assert count == 2
    
    def test_rejects_invalid_shas(self, tmp_path: Path):
        """Returns 0 if either SHA is invalid."""
        issues = [123]
        
        count = drain_revert.reopen_issues_with_label(
            issues, "invalid", "b" * 40, tmp_path, {}
        )
        assert count == 0
        
        count = drain_revert.reopen_issues_with_label(
            issues, "a" * 40, "invalid", tmp_path, {}
        )
        assert count == 0


class TestEnsureDrainRevertedLabelExists:
    """Tests for ensure_drain_reverted_label_exists function."""
    
    def test_label_already_exists(self, tmp_path: Path):
        """Returns True when label already exists."""
        check_result = MagicMock()
        check_result.returncode = 0
        check_result.stdout = '[{"name": "drain-reverted"}]'
        
        with patch("drain_revert.subprocess.run", return_value=check_result) as mock_run:
            result = drain_revert.ensure_drain_reverted_label_exists(tmp_path, {})
            
            assert result is True
            # Should only check, not create
            assert mock_run.call_count == 1
    
    def test_creates_missing_label(self, tmp_path: Path):
        """Creates label when it doesn't exist."""
        check_result = MagicMock()
        check_result.returncode = 0
        check_result.stdout = '[]'
        
        create_result = MagicMock()
        create_result.returncode = 0
        
        with patch("drain_revert.subprocess.run", side_effect=[check_result, create_result]) as mock_run:
            result = drain_revert.ensure_drain_reverted_label_exists(tmp_path, {})
            
            assert result is True
            assert mock_run.call_count == 2
            
            # Verify create command includes correct color and description
            create_call = mock_run.call_args_list[1][0][0]
            assert "B60205" in create_call  # Red color
            assert "--description" in create_call
    
    def test_returns_false_on_error(self, tmp_path: Path):
        """Returns False when gh commands fail."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        
        with patch("drain_revert.subprocess.run", return_value=mock_result):
            result = drain_revert.ensure_drain_reverted_label_exists(tmp_path, {})
            assert result is False