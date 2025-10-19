"""Unit tests for auto_test.py hook"""

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

from auto_test import detect_test_framework, run_pytest, run_jest, run_vitest, run_npm_test, run_go_test


class TestDetectTestFramework:
    """Test framework detection logic."""

    def test_detects_pytest_from_pytest_ini(self, tmp_path, monkeypatch):
        """Test detection of pytest from pytest.ini."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pytest.ini").touch()
        language, framework = detect_test_framework()
        assert language == "python"
        assert framework == "pytest"

    def test_detects_pytest_from_pyproject_toml(self, tmp_path, monkeypatch):
        """Test detection of pytest from pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").touch()
        language, framework = detect_test_framework()
        assert language == "python"
        assert framework == "pytest"

    def test_detects_jest_from_jest_config_js(self, tmp_path, monkeypatch):
        """Test detection of jest from jest.config.js."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "jest.config.js").touch()
        language, framework = detect_test_framework()
        assert language == "javascript"
        assert framework == "jest"

    def test_detects_jest_from_jest_config_ts(self, tmp_path, monkeypatch):
        """Test detection of jest from jest.config.ts."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "jest.config.ts").touch()
        language, framework = detect_test_framework()
        assert language == "javascript"
        assert framework == "jest"

    def test_detects_vitest_from_vitest_config_js(self, tmp_path, monkeypatch):
        """Test detection of vitest from vitest.config.js."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "vitest.config.js").touch()
        language, framework = detect_test_framework()
        assert language == "javascript"
        assert framework == "vitest"

    def test_detects_npm_from_package_json(self, tmp_path, monkeypatch):
        """Test fallback to npm from package.json."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "package.json").touch()
        language, framework = detect_test_framework()
        assert language == "javascript"
        assert framework == "npm"

    def test_detects_go_test_from_go_mod(self, tmp_path, monkeypatch):
        """Test detection of go test from go.mod."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "go.mod").touch()
        language, framework = detect_test_framework()
        assert language == "go"
        assert framework == "go-test"

    def test_returns_unknown_for_no_framework(self, tmp_path, monkeypatch):
        """Test returns unknown when no framework files found."""
        monkeypatch.chdir(tmp_path)
        language, framework = detect_test_framework()
        assert language == "unknown"
        assert framework == "unknown"


class TestRunPytest:
    """Test pytest runner."""

    @patch("subprocess.run")
    def test_run_pytest_success(self, mock_run):
        """Test successful pytest execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr=""
        )

        result = run_pytest()

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pytest" in call_args
        assert "--cov=src" in call_args

    @patch("subprocess.run")
    def test_run_pytest_failure(self, mock_run):
        """Test pytest execution with test failures."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Some tests failed",
            stderr="Error details"
        )

        result = run_pytest()

        assert result is False

    @patch("subprocess.run")
    def test_run_pytest_missing_tool(self, mock_run):
        """Test handling of missing pytest."""
        mock_run.side_effect = FileNotFoundError()

        result = run_pytest()

        assert result is False


class TestRunJest:
    """Test jest runner."""

    @patch("subprocess.run")
    def test_run_jest_success(self, mock_run):
        """Test successful jest execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr=""
        )

        result = run_jest()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "jest" in call_args
        assert "--coverage" in call_args

    @patch("subprocess.run")
    def test_run_jest_failure(self, mock_run):
        """Test jest execution with failures."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Tests failed",
            stderr=""
        )

        result = run_jest()

        assert result is False

    @patch("subprocess.run")
    def test_run_jest_missing_tool(self, mock_run):
        """Test handling of missing jest."""
        mock_run.side_effect = FileNotFoundError()

        result = run_jest()

        assert result is False


class TestRunVitest:
    """Test vitest runner."""

    @patch("subprocess.run")
    def test_run_vitest_success(self, mock_run):
        """Test successful vitest execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr=""
        )

        result = run_vitest()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "vitest" in call_args
        assert "--coverage" in call_args

    @patch("subprocess.run")
    def test_run_vitest_missing_tool(self, mock_run):
        """Test handling of missing vitest."""
        mock_run.side_effect = FileNotFoundError()

        result = run_vitest()

        assert result is False


class TestRunNpmTest:
    """Test npm test runner."""

    @patch("subprocess.run")
    def test_run_npm_test_success(self, mock_run):
        """Test successful npm test execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Tests passed",
            stderr=""
        )

        result = run_npm_test()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "npm" in call_args
        assert "test" in call_args

    @patch("subprocess.run")
    def test_run_npm_test_missing_npm(self, mock_run):
        """Test handling of missing npm."""
        mock_run.side_effect = FileNotFoundError()

        result = run_npm_test()

        assert result is False


class TestRunGoTest:
    """Test go test runner."""

    @patch("subprocess.run")
    def test_run_go_test_success(self, mock_run):
        """Test successful go test execution with good coverage."""
        # Mock both test run and coverage tool
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="PASS", stderr=""),
            MagicMock(
                returncode=0,
                stdout="coverage: 85.2% of statements\ntotal:          (statements)    85.2%",
                stderr=""
            )
        ]

        result = run_go_test()

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_run_go_test_low_coverage(self, mock_run):
        """Test go test with coverage below threshold."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="PASS", stderr=""),
            MagicMock(
                returncode=0,
                stdout="coverage: 65.0% of statements\ntotal:          (statements)    65.0%",
                stderr=""
            )
        ]

        result = run_go_test()

        assert result is False

    @patch("subprocess.run")
    def test_run_go_test_failures(self, mock_run):
        """Test go test with test failures."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="FAIL",
            stderr="Test failed"
        )

        result = run_go_test()

        assert result is False

    @patch("subprocess.run")
    def test_run_go_test_missing_go(self, mock_run):
        """Test handling of missing go."""
        mock_run.side_effect = FileNotFoundError()

        result = run_go_test()

        assert result is False
