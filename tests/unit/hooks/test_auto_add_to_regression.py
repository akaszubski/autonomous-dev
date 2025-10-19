"""Unit tests for auto_add_to_regression.py hook"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

from auto_add_to_regression import (
    detect_commit_type,
    check_tests_passing,
    generate_feature_regression_test,
)


class TestDetectCommitType:
    """Test commit type detection logic."""

    def test_detects_bugfix_from_fix_bug(self):
        """Test detection of bugfix from 'fix bug' keyword."""
        assert detect_commit_type("fix bug in authentication") == "bugfix"

    def test_detects_bugfix_from_bug_fix(self):
        """Test detection of bugfix from 'bug fix' keyword."""
        assert detect_commit_type("bug fix for login issue") == "bugfix"

    def test_detects_bugfix_from_issue(self):
        """Test detection of bugfix from 'issue' keyword."""
        assert detect_commit_type("fix issue with database") == "bugfix"

    def test_detects_bugfix_from_error(self):
        """Test detection of bugfix from 'error' keyword."""
        assert detect_commit_type("fix error in validation") == "bugfix"

    def test_detects_bugfix_from_crash(self):
        """Test detection of bugfix from 'crash' keyword."""
        assert detect_commit_type("fix crash on startup") == "bugfix"

    def test_detects_optimization(self):
        """Test detection of optimization commits."""
        assert detect_commit_type("optimize database queries") == "optimization"
        assert detect_commit_type("improve performance") == "optimization"
        assert detect_commit_type("make it faster") == "optimization"

    def test_detects_feature(self):
        """Test detection of feature commits."""
        assert detect_commit_type("implement user login") == "feature"
        assert detect_commit_type("add feature for search") == "feature"
        assert detect_commit_type("create new API") == "feature"

    def test_returns_unknown_for_ambiguous(self):
        """Test returns unknown for ambiguous commits."""
        assert detect_commit_type("update documentation") == "unknown"
        assert detect_commit_type("refactor code") == "unknown"

    def test_case_insensitive_detection(self):
        """Test that detection is case insensitive."""
        assert detect_commit_type("FIX BUG in code") == "bugfix"
        assert detect_commit_type("OPTIMIZE performance") == "optimization"
        assert detect_commit_type("IMPLEMENT feature") == "feature"


class TestCheckTestsPassing:
    """Test checking if tests are passing."""

    @patch("subprocess.run")
    def test_returns_true_when_tests_pass(self, mock_run, tmp_path, monkeypatch):
        """Test returns (True, message) when tests pass."""
        # Create necessary directory structure
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_module.py").touch()

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr=""
        )

        file_path = Path("src/module.py")
        passing, message = check_tests_passing(file_path)

        assert passing is True
        assert "passing" in message.lower()

    @patch("subprocess.run")
    def test_returns_false_when_tests_fail(self, mock_run, tmp_path, monkeypatch):
        """Test returns (False, output) when tests fail."""
        # Create necessary directory structure
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_module.py").touch()

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Tests failed",
            stderr=""
        )

        file_path = Path("src/module.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "failed" in message.lower()

    def test_returns_false_when_no_tests_exist(self, tmp_path):
        """Test returns (False, message) when no tests exist."""
        file_path = tmp_path / "module.py"

        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "No tests exist" in message

    @patch("subprocess.run")
    def test_handles_exception(self, mock_run, tmp_path, monkeypatch):
        """Test handling of test execution exception."""
        # Create necessary directory structure
        tests_dir = tmp_path / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_module.py").touch()

        monkeypatch.setattr("auto_add_to_regression.TESTS_DIR", tmp_path / "tests")

        mock_run.side_effect = Exception("Test error")

        file_path = Path("src/module.py")
        passing, message = check_tests_passing(file_path)

        assert passing is False
        assert "Error running tests" in message


class TestGenerateFeatureRegressionTest:
    """Test feature regression test generation."""

    def test_creates_test_file_with_timestamp(self):
        """Test that test file includes timestamp."""
        file_path = Path("src/authentication.py")
        user_prompt = "implement user login"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "test_feature_authentication" in str(test_file)
        assert "regression" in str(test_file)
        # Timestamp should be in filename (YYYYMMDD format)
        assert any(char.isdigit() for char in str(test_file))

    def test_includes_feature_description_in_content(self):
        """Test that generated content includes feature description."""
        file_path = Path("src/payment.py")
        user_prompt = "implement payment processing with Stripe"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "payment processing" in content.lower()
        assert "implement" in content.lower()

    def test_includes_regression_documentation(self):
        """Test that generated content includes regression documentation."""
        file_path = Path("src/module.py")
        user_prompt = "add feature"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "Regression test" in content
        assert "regress" in content.lower()
        assert "continues to work" in content.lower()

    def test_includes_creation_timestamp(self):
        """Test that generated content includes creation timestamp."""
        file_path = Path("src/module.py")
        user_prompt = "add feature"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "Created:" in content
        # Should have date format (YYYY-MM-DD)
        assert "-" in content

    def test_includes_test_functions(self):
        """Test that generated content includes test function stubs."""
        file_path = Path("src/module.py")
        user_prompt = "add feature"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "def test_feature_baseline" in content
        assert "def test_feature_edge_cases" in content
        assert "pytest" in content

    def test_uses_module_name(self):
        """Test that module name is used in test file path."""
        file_path = Path("src/user_manager.py")
        user_prompt = "add feature"

        test_file, content = generate_feature_regression_test(file_path, user_prompt)

        assert "user_manager" in str(test_file)
