"""
Unit tests for stop_quality_gate.py hook (Stop lifecycle).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test environment variable checking (ENFORCE_QUALITY_GATE)
- Test project tool detection (pytest, ruff, mypy)
- Test parallel quality check execution
- Test result formatting (stderr output)
- Test graceful degradation (missing tools)
- Test main entry point and exit codes
- Achieve 95%+ code coverage

Hook Type: Stop
Trigger: After every turn/response completes
Condition: Always runs (non-blocking quality feedback)
Exit Codes: Always EXIT_SUCCESS (0) - Stop hooks cannot block

Date: 2026-01-01
Feature: End-of-turn quality gates (Issue #177)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
from subprocess import CompletedProcess, CalledProcessError, TimeoutExpired
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

# Import will fail - hook doesn't exist yet (TDD!)
try:
    from stop_quality_gate import (
        should_enforce_quality_gate,
        detect_project_tools,
        run_quality_checks,
        format_results,
        main,
    )
    from hook_exit_codes import EXIT_SUCCESS
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Environment Variable Checking
# =============================================================================

class TestShouldEnforceQualityGate:
    """Test ENFORCE_QUALITY_GATE environment variable checking."""

    def test_enforce_when_env_var_true(self):
        """Should enforce when ENFORCE_QUALITY_GATE=true."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "true"}):
            assert should_enforce_quality_gate() is True

    def test_enforce_when_env_var_1(self):
        """Should enforce when ENFORCE_QUALITY_GATE=1."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "1"}):
            assert should_enforce_quality_gate() is True

    def test_enforce_when_env_var_yes(self):
        """Should enforce when ENFORCE_QUALITY_GATE=yes."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "yes"}):
            assert should_enforce_quality_gate() is True

    def test_enforce_case_insensitive(self):
        """Should be case-insensitive for env var values."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "TRUE"}):
            assert should_enforce_quality_gate() is True
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "Yes"}):
            assert should_enforce_quality_gate() is True
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "1"}):
            assert should_enforce_quality_gate() is True

    def test_no_enforce_when_env_var_false(self):
        """Should not enforce when ENFORCE_QUALITY_GATE=false."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "false"}):
            assert should_enforce_quality_gate() is False

    def test_no_enforce_when_env_var_0(self):
        """Should not enforce when ENFORCE_QUALITY_GATE=0."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "0"}):
            assert should_enforce_quality_gate() is False

    def test_no_enforce_when_env_var_no(self):
        """Should not enforce when ENFORCE_QUALITY_GATE=no."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "no"}):
            assert should_enforce_quality_gate() is False

    def test_default_to_true_when_env_var_not_set(self):
        """Should default to True (enabled) when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert should_enforce_quality_gate() is True

    def test_default_to_true_when_env_var_empty(self):
        """Should default to True when env var is empty string."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": ""}):
            assert should_enforce_quality_gate() is True


# =============================================================================
# Test Tool Detection
# =============================================================================

class TestDetectProjectTools:
    """Test detection of quality tools (pytest, ruff, mypy) in project."""

    def test_detect_pytest_from_pytest_ini(self, tmp_path):
        """Should detect pytest from pytest.ini file."""
        (tmp_path / "pytest.ini").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["pytest"]["available"] is True
        assert tools["pytest"]["config_file"] == "pytest.ini"

    def test_detect_pytest_from_pyproject_toml(self, tmp_path):
        """Should detect pytest from pyproject.toml with [tool.pytest] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']")

        tools = detect_project_tools(tmp_path)

        assert tools["pytest"]["available"] is True
        assert tools["pytest"]["config_file"] == "pyproject.toml"

    def test_detect_pytest_from_setup_cfg(self, tmp_path):
        """Should detect pytest from setup.cfg with [tool:pytest] section."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("[tool:pytest]\ntestpaths = tests")

        tools = detect_project_tools(tmp_path)

        assert tools["pytest"]["available"] is True
        assert tools["pytest"]["config_file"] == "setup.cfg"

    def test_detect_ruff_from_ruff_toml(self, tmp_path):
        """Should detect ruff from ruff.toml file."""
        (tmp_path / "ruff.toml").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["ruff"]["available"] is True
        assert tools["ruff"]["config_file"] == "ruff.toml"

    def test_detect_ruff_from_dot_ruff_toml(self, tmp_path):
        """Should detect ruff from .ruff.toml file."""
        (tmp_path / ".ruff.toml").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["ruff"]["available"] is True
        assert tools["ruff"]["config_file"] == ".ruff.toml"

    def test_detect_ruff_from_pyproject_toml(self, tmp_path):
        """Should detect ruff from pyproject.toml with [tool.ruff] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 120")

        tools = detect_project_tools(tmp_path)

        assert tools["ruff"]["available"] is True
        assert tools["ruff"]["config_file"] == "pyproject.toml"

    def test_detect_mypy_from_mypy_ini(self, tmp_path):
        """Should detect mypy from mypy.ini file."""
        (tmp_path / "mypy.ini").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["mypy"]["available"] is True
        assert tools["mypy"]["config_file"] == "mypy.ini"

    def test_detect_mypy_from_dot_mypy_ini(self, tmp_path):
        """Should detect mypy from .mypy.ini file."""
        (tmp_path / ".mypy.ini").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["mypy"]["available"] is True
        assert tools["mypy"]["config_file"] == ".mypy.ini"

    def test_detect_mypy_from_pyproject_toml(self, tmp_path):
        """Should detect mypy from pyproject.toml with [tool.mypy] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.mypy]\npython_version = '3.9'")

        tools = detect_project_tools(tmp_path)

        assert tools["mypy"]["available"] is True
        assert tools["mypy"]["config_file"] == "pyproject.toml"

    def test_detect_mypy_from_setup_cfg(self, tmp_path):
        """Should detect mypy from setup.cfg with [mypy] section."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("[mypy]\npython_version = 3.9")

        tools = detect_project_tools(tmp_path)

        assert tools["mypy"]["available"] is True
        assert tools["mypy"]["config_file"] == "setup.cfg"

    def test_detect_multiple_tools(self, tmp_path):
        """Should detect multiple tools in same project."""
        (tmp_path / "pytest.ini").touch()
        (tmp_path / "ruff.toml").touch()
        (tmp_path / "mypy.ini").touch()

        tools = detect_project_tools(tmp_path)

        assert tools["pytest"]["available"] is True
        assert tools["ruff"]["available"] is True
        assert tools["mypy"]["available"] is True

    def test_no_tools_detected_in_empty_project(self, tmp_path):
        """Should return all tools unavailable when no config files found."""
        tools = detect_project_tools(tmp_path)

        assert tools["pytest"]["available"] is False
        assert tools["ruff"]["available"] is False
        assert tools["mypy"]["available"] is False
        assert tools["pytest"]["config_file"] is None
        assert tools["ruff"]["config_file"] is None
        assert tools["mypy"]["config_file"] is None

    def test_prioritize_tool_specific_config_files(self, tmp_path):
        """Should prioritize tool-specific config over pyproject.toml."""
        # Create both pytest.ini and pyproject.toml with pytest config
        (tmp_path / "pytest.ini").touch()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']")

        tools = detect_project_tools(tmp_path)

        # Should prefer pytest.ini over pyproject.toml
        assert tools["pytest"]["config_file"] == "pytest.ini"

    def test_detect_tools_returns_dict_structure(self, tmp_path):
        """Should return consistent dict structure for all tools."""
        tools = detect_project_tools(tmp_path)

        # Verify structure
        assert "pytest" in tools
        assert "ruff" in tools
        assert "mypy" in tools

        for tool_name, tool_info in tools.items():
            assert "available" in tool_info
            assert "config_file" in tool_info
            assert isinstance(tool_info["available"], bool)
            assert tool_info["config_file"] is None or isinstance(tool_info["config_file"], str)


# =============================================================================
# Test Quality Check Execution
# =============================================================================

class TestRunQualityChecks:
    """Test parallel execution of quality checks (pytest, ruff, mypy)."""

    @patch("subprocess.run")
    def test_run_all_checks_when_all_available(self, mock_run):
        """Should run pytest, ruff, mypy when all tools available."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "mypy": {"available": True, "config_file": "mypy.ini"},
        }

        # Mock successful runs for all tools
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        results = run_quality_checks(tools)

        # Should run all 3 tools
        assert mock_run.call_count == 3
        assert results["pytest"]["ran"] is True
        assert results["ruff"]["ran"] is True
        assert results["mypy"]["ran"] is True
        assert results["pytest"]["passed"] is True
        assert results["ruff"]["passed"] is True
        assert results["mypy"]["passed"] is True

    @patch("subprocess.run")
    def test_run_pytest_with_correct_args(self, mock_run):
        """Should run pytest with minimal verbosity flags."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        run_quality_checks(tools)

        # Check pytest command
        pytest_call = mock_run.call_args_list[0][0][0]
        assert "pytest" in pytest_call
        assert "--tb=line" in pytest_call
        assert "-q" in pytest_call

    @patch("subprocess.run")
    def test_run_ruff_with_correct_args(self, mock_run):
        """Should run ruff check command."""
        tools = {
            "pytest": {"available": False, "config_file": None},
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "mypy": {"available": False, "config_file": None},
        }

        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        run_quality_checks(tools)

        # Check ruff command
        ruff_call = mock_run.call_args_list[0][0][0]
        assert "ruff" in ruff_call
        assert "check" in ruff_call

    @patch("subprocess.run")
    def test_run_mypy_with_correct_args(self, mock_run):
        """Should run mypy on source directories."""
        tools = {
            "pytest": {"available": False, "config_file": None},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": True, "config_file": "mypy.ini"},
        }

        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        run_quality_checks(tools)

        # Check mypy command
        mypy_call = mock_run.call_args_list[0][0][0]
        assert "mypy" in mypy_call
        assert "." in mypy_call  # Check current directory

    @patch("subprocess.run")
    def test_detect_pytest_failures(self, mock_run):
        """Should detect when pytest tests fail."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        # Mock pytest failure
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="FAILED tests/test_foo.py::test_bar"
        )

        results = run_quality_checks(tools)

        assert results["pytest"]["ran"] is True
        assert results["pytest"]["passed"] is False
        assert results["pytest"]["returncode"] == 1
        assert "FAILED" in results["pytest"]["stderr"]

    @patch("subprocess.run")
    def test_detect_ruff_violations(self, mock_run):
        """Should detect when ruff finds style violations."""
        tools = {
            "pytest": {"available": False, "config_file": None},
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "mypy": {"available": False, "config_file": None},
        }

        # Mock ruff violations
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="foo.py:10:5: E501 Line too long", stderr=""
        )

        results = run_quality_checks(tools)

        assert results["ruff"]["ran"] is True
        assert results["ruff"]["passed"] is False
        assert results["ruff"]["returncode"] == 1
        assert "E501" in results["ruff"]["stdout"]

    @patch("subprocess.run")
    def test_detect_mypy_type_errors(self, mock_run):
        """Should detect when mypy finds type errors."""
        tools = {
            "pytest": {"available": False, "config_file": None},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": True, "config_file": "mypy.ini"},
        }

        # Mock mypy type errors
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="foo.py:10: error: Incompatible types", stderr=""
        )

        results = run_quality_checks(tools)

        assert results["mypy"]["ran"] is True
        assert results["mypy"]["passed"] is False
        assert results["mypy"]["returncode"] == 1
        assert "error:" in results["mypy"]["stdout"]

    @patch("subprocess.run")
    def test_skip_unavailable_tools(self, mock_run):
        """Should skip tools marked as unavailable."""
        tools = {
            "pytest": {"available": False, "config_file": None},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        results = run_quality_checks(tools)

        # Should not run any subprocess
        assert mock_run.call_count == 0
        assert results["pytest"]["ran"] is False
        assert results["ruff"]["ran"] is False
        assert results["mypy"]["ran"] is False

    @patch("subprocess.run")
    def test_handle_tool_not_found_error(self, mock_run):
        """Should gracefully handle FileNotFoundError when tool not installed."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        # Simulate pytest not installed
        mock_run.side_effect = FileNotFoundError("pytest: command not found")

        results = run_quality_checks(tools)

        assert results["pytest"]["ran"] is True
        assert results["pytest"]["passed"] is False
        assert "not found" in results["pytest"]["error"].lower()

    @patch("subprocess.run")
    def test_handle_timeout_error(self, mock_run):
        """Should gracefully handle TimeoutExpired when tool hangs."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        # Simulate timeout
        mock_run.side_effect = TimeoutExpired(cmd="pytest", timeout=60)

        results = run_quality_checks(tools)

        assert results["pytest"]["ran"] is True
        assert results["pytest"]["passed"] is False
        assert "timeout" in results["pytest"]["error"].lower()

    @patch("subprocess.run")
    def test_handle_permission_error(self, mock_run):
        """Should gracefully handle PermissionError."""
        tools = {
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "pytest": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        # Simulate permission error
        mock_run.side_effect = PermissionError("Permission denied")

        results = run_quality_checks(tools)

        assert results["ruff"]["ran"] is True
        assert results["ruff"]["passed"] is False
        assert "permission" in results["ruff"]["error"].lower()

    @patch("subprocess.run")
    def test_capture_stdout_and_stderr(self, mock_run):
        """Should capture both stdout and stderr from tools."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=1,
            stdout="test output here",
            stderr="error output here",
        )

        results = run_quality_checks(tools)

        assert results["pytest"]["stdout"] == "test output here"
        assert results["pytest"]["stderr"] == "error output here"

    @patch("subprocess.run")
    def test_timeout_set_to_60_seconds(self, mock_run):
        """Should set 60 second timeout for all tools."""
        tools = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "mypy": {"available": True, "config_file": "mypy.ini"},
        }

        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        run_quality_checks(tools)

        # Check timeout parameter for all calls
        for call_args in mock_run.call_args_list:
            assert call_args[1]["timeout"] == 60


# =============================================================================
# Test Result Formatting
# =============================================================================

class TestFormatResults:
    """Test formatting of quality check results for stderr output."""

    def test_format_all_passed(self):
        """Should format success message when all checks pass."""
        results = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": True, "passed": True, "returncode": 0},
            "mypy": {"ran": True, "passed": True, "returncode": 0},
        }

        output = format_results(results)

        assert "✅" in output or "PASS" in output
        assert "pytest" in output.lower()
        assert "ruff" in output.lower()
        assert "mypy" in output.lower()

    def test_format_pytest_failed(self):
        """Should format failure message when pytest fails."""
        results = {
            "pytest": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stderr": "FAILED tests/test_foo.py::test_bar",
            },
            "ruff": {"ran": True, "passed": True, "returncode": 0},
            "mypy": {"ran": True, "passed": True, "returncode": 0},
        }

        output = format_results(results)

        assert "❌" in output or "FAIL" in output
        assert "pytest" in output.lower()
        assert "test_foo.py" in output

    def test_format_ruff_violations(self):
        """Should format violation message when ruff finds issues."""
        results = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stdout": "foo.py:10:5: E501 Line too long",
            },
            "mypy": {"ran": True, "passed": True, "returncode": 0},
        }

        output = format_results(results)

        assert "❌" in output or "FAIL" in output
        assert "ruff" in output.lower()
        assert "E501" in output

    def test_format_mypy_type_errors(self):
        """Should format error message when mypy finds type issues."""
        results = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": True, "passed": True, "returncode": 0},
            "mypy": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stdout": "foo.py:10: error: Incompatible types",
            },
        }

        output = format_results(results)

        assert "❌" in output or "FAIL" in output
        assert "mypy" in output.lower()
        assert "error:" in output.lower()

    def test_format_skipped_tools(self):
        """Should indicate when tools were skipped (not available)."""
        results = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }

        output = format_results(results)

        assert "⚠️" in output or "SKIP" in output
        assert "ruff" in output.lower()
        assert "mypy" in output.lower()

    def test_format_tool_not_found_error(self):
        """Should format error message when tool not installed."""
        results = {
            "pytest": {
                "ran": True,
                "passed": False,
                "error": "pytest: command not found",
            },
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }

        output = format_results(results)

        assert "⚠️" in output or "ERROR" in output
        assert "pytest" in output.lower()
        assert "not found" in output.lower()

    def test_format_multiple_failures(self):
        """Should format output when multiple tools fail."""
        results = {
            "pytest": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stderr": "FAILED tests/test_foo.py",
            },
            "ruff": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stdout": "E501 Line too long",
            },
            "mypy": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stdout": "error: Incompatible types",
            },
        }

        output = format_results(results)

        # Should show all failures
        assert output.count("❌") >= 3 or output.count("FAIL") >= 3
        assert "pytest" in output.lower()
        assert "ruff" in output.lower()
        assert "mypy" in output.lower()

    def test_format_no_tools_ran(self):
        """Should indicate when no tools ran (empty project)."""
        results = {
            "pytest": {"ran": False, "passed": None},
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }

        output = format_results(results)

        assert "⚠️" in output or "SKIP" in output or "No quality" in output

    def test_format_includes_header(self):
        """Should include header indicating quality gate check."""
        results = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }

        output = format_results(results)

        assert "Quality Gate" in output or "quality" in output.lower()


# =============================================================================
# Test Main Entry Point
# =============================================================================

class TestMainEntryPoint:
    """Test main() function - hook entry point."""

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("stop_quality_gate.detect_project_tools")
    @patch("stop_quality_gate.run_quality_checks")
    @patch("stop_quality_gate.format_results")
    @patch("sys.stderr.write")
    def test_main_runs_full_workflow_when_enabled(
        self,
        mock_stderr,
        mock_format,
        mock_run_checks,
        mock_detect,
        mock_should_enforce,
        tmp_path,
        monkeypatch,
    ):
        """Should run full quality gate workflow when enabled."""
        monkeypatch.chdir(tmp_path)

        # Setup mocks
        mock_should_enforce.return_value = True
        mock_detect.return_value = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": True, "config_file": "ruff.toml"},
            "mypy": {"available": False, "config_file": None},
        }
        mock_run_checks.return_value = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": True, "passed": True, "returncode": 0},
            "mypy": {"ran": False, "passed": None},
        }
        mock_format.return_value = "✅ All quality checks passed"

        # Run main
        exit_code = main()

        # Verify workflow
        assert exit_code == EXIT_SUCCESS
        mock_should_enforce.assert_called_once()
        mock_detect.assert_called_once()
        mock_run_checks.assert_called_once()
        mock_format.assert_called_once()
        mock_stderr.assert_called()

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("sys.stderr.write")
    def test_main_skips_when_disabled(self, mock_stderr, mock_should_enforce):
        """Should skip quality gate when ENFORCE_QUALITY_GATE=false."""
        mock_should_enforce.return_value = False

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        mock_should_enforce.assert_called_once()
        # Should write skip message to stderr
        assert mock_stderr.called

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("stop_quality_gate.detect_project_tools")
    @patch("stop_quality_gate.run_quality_checks")
    @patch("stop_quality_gate.format_results")
    @patch("sys.stderr.write")
    def test_main_always_exits_success_even_on_failures(
        self,
        mock_stderr,
        mock_format,
        mock_run_checks,
        mock_detect,
        mock_should_enforce,
        tmp_path,
        monkeypatch,
    ):
        """Should always exit EXIT_SUCCESS (0) even when checks fail."""
        monkeypatch.chdir(tmp_path)

        # Setup mocks - simulate test failures
        mock_should_enforce.return_value = True
        mock_detect.return_value = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }
        mock_run_checks.return_value = {
            "pytest": {
                "ran": True,
                "passed": False,
                "returncode": 1,
                "stderr": "FAILED",
            },
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }
        mock_format.return_value = "❌ pytest: FAILED"

        # Run main
        exit_code = main()

        # Should ALWAYS exit 0 (Stop hooks cannot block)
        assert exit_code == EXIT_SUCCESS

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("stop_quality_gate.detect_project_tools")
    @patch("sys.stderr.write")
    def test_main_handles_exceptions_gracefully(
        self, mock_stderr, mock_detect, mock_should_enforce
    ):
        """Should catch exceptions and exit EXIT_SUCCESS (graceful degradation)."""
        mock_should_enforce.return_value = True
        mock_detect.side_effect = Exception("Unexpected error")

        exit_code = main()

        # Should still exit 0 (non-blocking)
        assert exit_code == EXIT_SUCCESS
        # Should write error to stderr
        assert mock_stderr.called

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("stop_quality_gate.detect_project_tools")
    @patch("stop_quality_gate.run_quality_checks")
    @patch("sys.stderr.write")
    def test_main_writes_output_to_stderr(
        self, mock_stderr, mock_run_checks, mock_detect, mock_should_enforce, tmp_path, monkeypatch
    ):
        """Should write formatted output to stderr (Claude surfaces stderr)."""
        monkeypatch.chdir(tmp_path)

        mock_should_enforce.return_value = True
        mock_detect.return_value = {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }
        mock_run_checks.return_value = {
            "pytest": {"ran": True, "passed": True, "returncode": 0},
            "ruff": {"ran": False, "passed": None},
            "mypy": {"ran": False, "passed": None},
        }

        main()

        # Should write to stderr
        assert mock_stderr.called
        # Check that quality gate output was written
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert len(stderr_output) > 0


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""

    @patch("subprocess.run")
    @patch("sys.stderr.write")
    def test_full_workflow_all_tools_pass(
        self, mock_stderr, mock_run, tmp_path, monkeypatch
    ):
        """Test complete workflow when all tools pass."""
        monkeypatch.chdir(tmp_path)

        # Create config files
        (tmp_path / "pytest.ini").touch()
        (tmp_path / "ruff.toml").touch()
        (tmp_path / "mypy.ini").touch()

        # Mock all tools succeed
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="OK", stderr=""
        )

        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "true"}):
            exit_code = main()

        assert exit_code == EXIT_SUCCESS
        assert mock_run.call_count == 3  # pytest, ruff, mypy
        assert mock_stderr.called

    @patch("subprocess.run")
    @patch("sys.stderr.write")
    def test_full_workflow_pytest_fails(
        self, mock_stderr, mock_run, tmp_path, monkeypatch
    ):
        """Test workflow when pytest fails but hook still exits 0."""
        monkeypatch.chdir(tmp_path)

        (tmp_path / "pytest.ini").touch()

        # Mock pytest failure
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="FAILED tests/test_foo.py"
        )

        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "true"}):
            exit_code = main()

        # Should exit 0 even on failure (Stop hooks cannot block)
        assert exit_code == EXIT_SUCCESS
        assert mock_stderr.called
        # Verify failure message in stderr
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "FAIL" in stderr_output or "❌" in stderr_output

    @patch("sys.stderr.write")
    def test_full_workflow_disabled(self, mock_stderr, tmp_path, monkeypatch):
        """Test workflow when quality gate disabled."""
        monkeypatch.chdir(tmp_path)

        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "false"}):
            exit_code = main()

        assert exit_code == EXIT_SUCCESS
        assert mock_stderr.called
        # Should write skip message
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "skip" in stderr_output.lower() or "disabled" in stderr_output.lower()

    @patch("subprocess.run")
    @patch("sys.stderr.write")
    def test_full_workflow_no_tools_available(
        self, mock_stderr, mock_run, tmp_path, monkeypatch
    ):
        """Test workflow when no quality tools configured."""
        monkeypatch.chdir(tmp_path)

        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "true"}):
            exit_code = main()

        # Should exit 0 even with no tools
        assert exit_code == EXIT_SUCCESS
        # Should not run any subprocess
        assert mock_run.call_count == 0
        assert mock_stderr.called


# =============================================================================
# Test Exit Code Compliance
# =============================================================================

class TestExitCodeCompliance:
    """Test compliance with Stop lifecycle exit code constraints."""

    def test_main_always_returns_exit_success(self):
        """Should always return EXIT_SUCCESS (Stop hooks cannot block)."""
        with patch.dict(os.environ, {"ENFORCE_QUALITY_GATE": "false"}):
            exit_code = main()

        assert exit_code == EXIT_SUCCESS
        assert exit_code == 0

    @patch("stop_quality_gate.should_enforce_quality_gate")
    @patch("stop_quality_gate.detect_project_tools")
    def test_main_returns_exit_success_on_exception(
        self, mock_detect, mock_should_enforce
    ):
        """Should return EXIT_SUCCESS even when exceptions occur."""
        mock_should_enforce.return_value = True
        mock_detect.side_effect = Exception("Unexpected error")

        exit_code = main()

        assert exit_code == EXIT_SUCCESS

    def test_exit_success_constant_equals_zero(self):
        """Should verify EXIT_SUCCESS constant equals 0."""
        assert EXIT_SUCCESS == 0
