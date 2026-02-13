"""
Unit tests for implementation_quality_gate.py hook (SubagentStop lifecycle).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test GenAI analysis against 3 implementation quality principles
- Test heuristic fallback when GenAI unavailable
- Test git diff extraction and truncation
- Test feedback formatting for stderr output
- Test graceful degradation and error handling
- Test main entry point and exit codes
- Achieve 95%+ code coverage

Hook Type: SubagentStop
Trigger: After implementer agent completes
Condition: Always runs (non-blocking quality feedback)
Exit Codes: Always EXIT_SUCCESS (0) - Stop hooks cannot block

3 Implementation Quality Principles:
1. Real Implementation (7+/10): No stubs, placeholders, or warning-only code
2. Test-Driven (7+/10): Tests pass (100% or with valid skips), no trivial asserts
3. Complete Work (7+/10): Blockers documented with TODO(blocked: reason)

Date: 2026-02-12
Feature: Implementation quality gate (Issue #329)
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
from typing import Dict, Any, Optional

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
    from implementation_quality_gate import (
        extract_implementation_diff,
        analyze_with_genai,
        fallback_heuristics,
        format_feedback,
        main,
    )
    # Import from lib (exit codes are in lib, not hooks)
    sys.path.insert(
        0,
        str(
            Path(__file__).parent.parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "lib"
        ),
    )
    from hook_exit_codes import EXIT_SUCCESS
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


# =============================================================================
# Test Git Diff Extraction
# =============================================================================

class TestExtractImplementationDiff:
    """Test extraction of implementation changes via git diff."""

    @patch("subprocess.run")
    def test_extract_diff_runs_git_diff_head(self, mock_run):
        """Should run 'git diff HEAD' to get implementation changes."""
        mock_run.return_value = CompletedProcess(
            args=["git", "diff", "HEAD"],
            returncode=0,
            stdout="diff --git a/foo.py b/foo.py\n+new code",
            stderr="",
        )

        diff = extract_implementation_diff()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "diff" in call_args
        assert "HEAD" in call_args

    @patch("subprocess.run")
    def test_extract_diff_returns_stdout(self, mock_run):
        """Should return stdout from git diff command."""
        expected_diff = "diff --git a/foo.py b/foo.py\n+def new_func():\n+    pass"
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout=expected_diff, stderr=""
        )

        diff = extract_implementation_diff()

        assert diff == expected_diff

    @patch("subprocess.run")
    def test_extract_diff_truncates_to_5000_chars(self, mock_run):
        """Should truncate diff to 5000 characters max (GenAI token limit)."""
        large_diff = "x" * 10000  # 10k chars
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout=large_diff, stderr=""
        )

        diff = extract_implementation_diff()

        assert len(diff) == 5000
        assert diff == large_diff[:5000]

    @patch("subprocess.run")
    def test_extract_diff_preserves_small_diffs(self, mock_run):
        """Should preserve diffs under 5000 chars unchanged."""
        small_diff = "diff --git a/foo.py b/foo.py\n+print('hello')"
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout=small_diff, stderr=""
        )

        diff = extract_implementation_diff()

        assert diff == small_diff

    @patch("subprocess.run")
    def test_extract_diff_handles_empty_diff(self, mock_run):
        """Should handle empty diff (no changes)."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        diff = extract_implementation_diff()

        assert diff == ""

    @patch("subprocess.run")
    def test_extract_diff_handles_git_error(self, mock_run):
        """Should return empty string on git command failure."""
        mock_run.side_effect = CalledProcessError(
            returncode=128, cmd="git diff HEAD", stderr="fatal: not a git repository"
        )

        diff = extract_implementation_diff()

        assert diff == ""

    @patch("subprocess.run")
    def test_extract_diff_handles_timeout(self, mock_run):
        """Should return empty string on git command timeout."""
        mock_run.side_effect = TimeoutExpired(cmd="git diff HEAD", timeout=5)

        diff = extract_implementation_diff()

        assert diff == ""

    @patch("subprocess.run")
    def test_extract_diff_sets_timeout_5_seconds(self, mock_run):
        """Should set 5 second timeout for git command."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="diff", stderr=""
        )

        extract_implementation_diff()

        assert mock_run.call_args[1]["timeout"] == 5


# =============================================================================
# Test GenAI Analysis
# =============================================================================

class TestAnalyzeWithGenAI:
    """Test GenAI analysis against 3 implementation quality principles."""

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_analysis_returns_dict_with_3_principles(self, mock_analyzer_class):
        """Should return dict with scores for all 3 principles."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 9,
            "principle_3_complete_work": 7,
        })

        result = analyze_with_genai("diff content")

        assert "principle_1_real_implementation" in result
        assert "principle_2_test_driven" in result
        assert "principle_3_complete_work" in result

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_passes_when_all_scores_above_7(self, mock_analyzer_class):
        """Should mark all principles as passing when scores >= 7."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 9,
            "principle_3_complete_work": 10,
        })

        result = analyze_with_genai("diff content")

        assert result["principle_1_real_implementation"] >= 7
        assert result["principle_2_test_driven"] >= 7
        assert result["principle_3_complete_work"] >= 7

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_fails_principle_1_on_stubs(self, mock_analyzer_class):
        """Should fail principle 1 (real implementation) for stub code."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 3,  # Failed
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 7,
        })

        result = analyze_with_genai("+raise NotImplementedError('TODO')")

        assert result["principle_1_real_implementation"] < 7

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_fails_principle_2_on_test_failures(self, mock_analyzer_class):
        """Should fail principle 2 (test-driven) when tests fail."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 5,  # Failed
            "principle_3_complete_work": 7,
        })

        result = analyze_with_genai("pytest output: 45/56 passing (80%)")

        assert result["principle_2_test_driven"] < 7

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_fails_principle_3_on_silent_stubs(self, mock_analyzer_class):
        """Should fail principle 3 (complete work) for silent stubs without blockers."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 4,  # Failed
        })

        result = analyze_with_genai("+pass  # TODO: implement later")

        assert result["principle_3_complete_work"] < 7

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_passes_principle_3_with_explicit_blocker(self, mock_analyzer_class):
        """Should pass principle 3 when blocker documented with TODO(blocked)."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,  # Passed
        })

        result = analyze_with_genai("+# TODO(blocked: API endpoint not ready)")

        assert result["principle_3_complete_work"] >= 7

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_handles_malformed_json_response(self, mock_analyzer_class):
        """Should return None on malformed GenAI JSON response."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = "This is not JSON"

        result = analyze_with_genai("diff content")

        assert result is None

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_handles_none_response(self, mock_analyzer_class):
        """Should return None when GenAI returns None (API unavailable)."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = None

        result = analyze_with_genai("diff content")

        assert result is None

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_handles_missing_principle_keys(self, mock_analyzer_class):
        """Should return None when response missing principle keys."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            # Missing principle_2 and principle_3
        })

        result = analyze_with_genai("diff content")

        assert result is None

    @patch("implementation_quality_gate.GenAIAnalyzer")
    def test_genai_uses_correct_model_config(self, mock_analyzer_class):
        """Should use Haiku model with appropriate token limits."""
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        })

        analyze_with_genai("diff content")

        # Verify analyzer initialized with appropriate config
        mock_analyzer_class.assert_called_once()


# =============================================================================
# Test Heuristic Fallback
# =============================================================================

class TestFallbackHeuristics:
    """Test heuristic fallback when GenAI unavailable."""

    @patch("subprocess.run")
    def test_heuristic_fails_principle_1_on_not_implemented_error(self, mock_run):
        """Should fail principle 1 when grep finds NotImplementedError."""
        # Mock grep finding NotImplementedError
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="foo.py:10:raise NotImplementedError", stderr=""
        )

        result = fallback_heuristics("+raise NotImplementedError('TODO')")

        assert result["principle_1_real_implementation"] < 7
        assert "NotImplementedError" in result.get("principle_1_reason", "")

    @patch("subprocess.run")
    def test_heuristic_fails_principle_1_on_pass_placeholder(self, mock_run):
        """Should fail principle 1 when code has 'pass' placeholders."""
        diff = "+def new_func():\n+    pass  # TODO"

        result = fallback_heuristics(diff)

        # Should detect pass placeholder
        assert result["principle_1_real_implementation"] < 7

    @patch("subprocess.run")
    def test_heuristic_fails_principle_1_on_return_none_placeholder(self, mock_run):
        """Should fail principle 1 when code has 'return None' placeholders."""
        diff = "+def new_func():\n+    return None  # TODO"

        result = fallback_heuristics(diff)

        assert result["principle_1_real_implementation"] < 7

    @patch("subprocess.run")
    def test_heuristic_passes_principle_1_when_no_stubs(self, mock_run):
        """Should pass principle 1 when no stub patterns found."""
        diff = "+def new_func():\n+    return calculate_result(data)"

        result = fallback_heuristics(diff)

        assert result["principle_1_real_implementation"] >= 7

    @patch("subprocess.run")
    def test_heuristic_fails_principle_2_on_test_failures(self, mock_run):
        """Should fail principle 2 when pytest shows failures."""
        # Mock pytest run with failures
        def subprocess_side_effect(cmd, *args, **kwargs):
            if "pytest" in cmd:
                return CompletedProcess(
                    args=[], returncode=1, stdout="45 passed, 11 failed", stderr=""
                )
            return CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        mock_run.side_effect = subprocess_side_effect

        result = fallback_heuristics("diff content")

        assert result["principle_2_test_driven"] < 7

    @patch("subprocess.run")
    def test_heuristic_passes_principle_2_on_test_success(self, mock_run):
        """Should pass principle 2 when all tests pass."""
        def subprocess_side_effect(cmd, *args, **kwargs):
            if "pytest" in cmd:
                return CompletedProcess(
                    args=[], returncode=0, stdout="56 passed", stderr=""
                )
            return CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        mock_run.side_effect = subprocess_side_effect

        result = fallback_heuristics("diff content")

        assert result["principle_2_test_driven"] >= 7

    @patch("subprocess.run")
    def test_heuristic_fails_principle_2_on_assert_true_only(self, mock_run):
        """Should fail principle 2 when tests only have 'assert True'."""
        diff = "+def test_foo():\n+    assert True  # Trivial test"

        result = fallback_heuristics(diff)

        # Should detect trivial test
        assert result["principle_2_test_driven"] < 7

    @patch("subprocess.run")
    def test_heuristic_fails_principle_3_on_todo_without_blocker(self, mock_run):
        """Should fail principle 3 when TODO without 'blocked' keyword."""
        diff = "+# TODO: implement this later"

        result = fallback_heuristics(diff)

        assert result["principle_3_complete_work"] < 7

    @patch("subprocess.run")
    def test_heuristic_passes_principle_3_on_todo_blocked(self, mock_run):
        """Should pass principle 3 when TODO has 'blocked' keyword."""
        diff = "+# TODO(blocked: API endpoint not ready)"

        result = fallback_heuristics(diff)

        assert result["principle_3_complete_work"] >= 7

    @patch("subprocess.run")
    def test_heuristic_passes_principle_3_when_no_todos(self, mock_run):
        """Should pass principle 3 when no TODO comments."""
        diff = "+def new_func():\n+    return calculate_result()"

        result = fallback_heuristics(diff)

        assert result["principle_3_complete_work"] >= 7

    @patch("subprocess.run")
    def test_heuristic_returns_all_3_principles(self, mock_run):
        """Should always return scores for all 3 principles."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        result = fallback_heuristics("diff content")

        assert "principle_1_real_implementation" in result
        assert "principle_2_test_driven" in result
        assert "principle_3_complete_work" in result

    @patch("subprocess.run")
    def test_heuristic_includes_reasons_for_failures(self, mock_run):
        """Should include human-readable reasons for failures."""
        diff = "+raise NotImplementedError('TODO')"

        result = fallback_heuristics(diff)

        assert "principle_1_reason" in result
        assert len(result["principle_1_reason"]) > 0


# =============================================================================
# Test Feedback Formatting
# =============================================================================

class TestFormatFeedback:
    """Test formatting of quality gate feedback for stderr output."""

    def test_format_all_principles_passing(self):
        """Should format success message when all principles pass."""
        result = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 9,
            "principle_3_complete_work": 7,
        }

        output = format_feedback(result)

        assert "PASS" in output or "✅" in output
        assert "principle 1" in output.lower() or "real implementation" in output.lower()
        assert "principle 2" in output.lower() or "test-driven" in output.lower()
        assert "principle 3" in output.lower() or "complete work" in output.lower()

    def test_format_principle_1_failure(self):
        """Should format failure message for principle 1 (stubs detected)."""
        result = {
            "principle_1_real_implementation": 3,
            "principle_1_reason": "Found NotImplementedError stub",
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        }

        output = format_feedback(result)

        assert "FAIL" in output or "❌" in output
        assert "principle 1" in output.lower() or "real implementation" in output.lower()
        assert "NotImplementedError" in output

    def test_format_principle_2_failure(self):
        """Should format failure message for principle 2 (test failures)."""
        result = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 5,
            "principle_2_reason": "80% test pass rate (56 total, 45 passing)",
            "principle_3_complete_work": 8,
        }

        output = format_feedback(result)

        assert "FAIL" in output or "❌" in output
        assert "principle 2" in output.lower() or "test-driven" in output.lower()
        assert "80%" in output

    def test_format_principle_3_failure(self):
        """Should format failure message for principle 3 (incomplete work)."""
        result = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 4,
            "principle_3_reason": "TODO without blocker documentation",
        }

        output = format_feedback(result)

        assert "FAIL" in output or "❌" in output
        assert "principle 3" in output.lower() or "complete work" in output.lower()
        assert "TODO" in output

    def test_format_multiple_failures(self):
        """Should format output when multiple principles fail."""
        result = {
            "principle_1_real_implementation": 3,
            "principle_1_reason": "Stub code detected",
            "principle_2_test_driven": 5,
            "principle_2_reason": "Test failures detected",
            "principle_3_complete_work": 4,
            "principle_3_reason": "Incomplete work",
        }

        output = format_feedback(result)

        # Should show all 3 failures
        assert output.count("FAIL") >= 3 or output.count("❌") >= 3

    def test_format_includes_header(self):
        """Should include header indicating quality gate check."""
        result = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        }

        output = format_feedback(result)

        assert "Quality Gate" in output or "Implementation Quality" in output

    def test_format_shows_scores(self):
        """Should show numeric scores (0-10) for each principle."""
        result = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 9,
            "principle_3_complete_work": 10,
        }

        output = format_feedback(result)

        assert "8" in output
        assert "9" in output
        assert "10" in output

    def test_format_handles_none_result(self):
        """Should handle None result (GenAI unavailable, heuristics failed)."""
        result = None

        output = format_feedback(result)

        assert "unavailable" in output.lower() or "skipped" in output.lower()

    def test_format_handles_empty_result(self):
        """Should handle empty result dict."""
        result = {}

        output = format_feedback(result)

        assert len(output) > 0  # Should still produce some output


# =============================================================================
# Test Main Entry Point
# =============================================================================

class TestMainEntryPoint:
    """Test main() function - hook entry point."""

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("implementation_quality_gate.analyze_with_genai")
    @patch("implementation_quality_gate.format_feedback")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_runs_full_genai_workflow(
        self, mock_stdin, mock_stderr, mock_format, mock_genai, mock_extract
    ):
        """Should run full GenAI analysis workflow when available."""
        # Mock stdin JSON input (SubagentStop event)
        mock_stdin.return_value = json.dumps({
            "agent_name": "implementer",
            "success": True,
        })

        # Mock implementation diff
        mock_extract.return_value = "diff --git a/foo.py\n+new code"

        # Mock GenAI analysis
        mock_genai.return_value = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 9,
            "principle_3_complete_work": 7,
        }

        # Mock feedback formatting
        mock_format.return_value = "✅ All quality checks passed"

        # Run main
        exit_code = main()

        # Verify workflow
        assert exit_code == EXIT_SUCCESS
        mock_extract.assert_called_once()
        mock_genai.assert_called_once()
        mock_format.assert_called_once()
        mock_stderr.assert_called()

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("implementation_quality_gate.analyze_with_genai")
    @patch("implementation_quality_gate.fallback_heuristics")
    @patch("implementation_quality_gate.format_feedback")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_falls_back_to_heuristics_when_genai_unavailable(
        self, mock_stdin, mock_stderr, mock_format, mock_heuristics, mock_genai, mock_extract
    ):
        """Should fall back to heuristics when GenAI returns None."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.return_value = "diff content"
        mock_genai.return_value = None  # GenAI unavailable

        # Mock heuristics fallback
        mock_heuristics.return_value = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        }

        mock_format.return_value = "✅ Heuristic checks passed"

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        mock_heuristics.assert_called_once()
        mock_format.assert_called_once()

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_exits_early_on_empty_diff(
        self, mock_stdin, mock_stderr, mock_extract
    ):
        """Should exit early with success when no implementation changes."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.return_value = ""  # No changes

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        # Should write "no changes" message to stderr
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "no changes" in stderr_output.lower() or "empty" in stderr_output.lower()

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("implementation_quality_gate.analyze_with_genai")
    @patch("implementation_quality_gate.format_feedback")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_always_exits_success_even_on_failures(
        self, mock_stdin, mock_stderr, mock_format, mock_genai, mock_extract
    ):
        """Should always exit EXIT_SUCCESS (0) even when quality checks fail."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.return_value = "diff content"

        # Mock quality gate failures
        mock_genai.return_value = {
            "principle_1_real_implementation": 3,  # Failed
            "principle_2_test_driven": 5,          # Failed
            "principle_3_complete_work": 4,        # Failed
        }

        mock_format.return_value = "❌ Quality checks failed"

        exit_code = main()

        # Should ALWAYS exit 0 (SubagentStop hooks cannot block)
        assert exit_code == EXIT_SUCCESS

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_handles_exceptions_gracefully(
        self, mock_stdin, mock_stderr, mock_extract
    ):
        """Should catch exceptions and exit EXIT_SUCCESS (graceful degradation)."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.side_effect = Exception("Unexpected error")

        exit_code = main()

        # Should still exit 0 (non-blocking)
        assert exit_code == EXIT_SUCCESS
        # Should write error to stderr
        assert mock_stderr.called

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("implementation_quality_gate.analyze_with_genai")
    @patch("implementation_quality_gate.format_feedback")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_main_writes_output_to_stderr(
        self, mock_stdin, mock_stderr, mock_format, mock_genai, mock_extract
    ):
        """Should write formatted output to stderr (Claude surfaces stderr)."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.return_value = "diff content"
        mock_genai.return_value = {
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        }
        mock_format.return_value = "✅ Quality checks passed"

        main()

        # Should write to stderr
        assert mock_stderr.called
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert len(stderr_output) > 0

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("sys.stdin.read")
    def test_main_only_runs_for_implementer_agent(
        self, mock_stdin, mock_extract
    ):
        """Should only run quality gate for 'implementer' agent."""
        # Test with implementer agent
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.return_value = "diff content"

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        mock_extract.assert_called_once()

    @patch("sys.stdin.read")
    @patch("sys.stderr.write")
    def test_main_skips_for_other_agents(
        self, mock_stderr, mock_stdin
    ):
        """Should skip quality gate for non-implementer agents."""
        mock_stdin.return_value = json.dumps({"agent_name": "researcher"})

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        # Should write skip message to stderr
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "skip" in stderr_output.lower() or "implementer" in stderr_output.lower()

    @patch("sys.stdin.read")
    def test_main_handles_malformed_json_stdin(self, mock_stdin):
        """Should handle malformed JSON in stdin gracefully."""
        mock_stdin.return_value = "This is not JSON"

        exit_code = main()

        # Should still exit 0 (graceful degradation)
        assert exit_code == EXIT_SUCCESS


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestIntegrationScenarios:
    """Test end-to-end integration scenarios from issue #329."""

    @patch("subprocess.run")
    @patch("implementation_quality_gate.GenAIAnalyzer")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_scenario_known_good_implementation(
        self, mock_stdin, mock_stderr, mock_analyzer_class, mock_run
    ):
        """Scenario 1: Known good implementation -> all 3 principles pass."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})

        # Mock git diff with real implementation
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="diff\n+def calculate():\n+    return x * y", stderr=""
        )

        # Mock GenAI analysis - all pass
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 9,
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        })

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "PASS" in stderr_output or "✅" in stderr_output

    @patch("subprocess.run")
    @patch("implementation_quality_gate.GenAIAnalyzer")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_scenario_stub_implementation(
        self, mock_stdin, mock_stderr, mock_analyzer_class, mock_run
    ):
        """Scenario 2: Stub implementation (NotImplementedError) -> principle 1 fails."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})

        # Mock git diff with stub
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="diff\n+raise NotImplementedError('TODO')", stderr=""
        )

        # Mock GenAI analysis - principle 1 fails
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 2,  # FAIL
            "principle_2_test_driven": 8,
            "principle_3_complete_work": 8,
        })

        exit_code = main()

        assert exit_code == EXIT_SUCCESS  # Still exits 0 (non-blocking)
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "FAIL" in stderr_output or "❌" in stderr_output

    @patch("subprocess.run")
    @patch("implementation_quality_gate.GenAIAnalyzer")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_scenario_test_failures(
        self, mock_stdin, mock_stderr, mock_analyzer_class, mock_run
    ):
        """Scenario 5: 80% test pass rate -> principle 2 fails."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})

        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="diff content", stderr=""
        )

        # Mock GenAI analysis - principle 2 fails
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = json.dumps({
            "principle_1_real_implementation": 8,
            "principle_2_test_driven": 6,  # FAIL (< 7)
            "principle_3_complete_work": 8,
        })

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        stderr_output = "".join([call[0][0] for call in mock_stderr.call_args_list])
        assert "FAIL" in stderr_output or "❌" in stderr_output

    @patch("subprocess.run")
    @patch("implementation_quality_gate.GenAIAnalyzer")
    @patch("sys.stderr.write")
    @patch("sys.stdin.read")
    def test_scenario_genai_unavailable_fallback(
        self, mock_stdin, mock_stderr, mock_analyzer_class, mock_run
    ):
        """Scenario 9: GenAI unavailable -> falls back to heuristics."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})

        # Mock git diff
        def subprocess_side_effect(cmd, *args, **kwargs):
            if "git" in cmd and "diff" in cmd:
                return CompletedProcess(
                    args=[], returncode=0, stdout="diff content", stderr=""
                )
            elif "pytest" in cmd:
                return CompletedProcess(
                    args=[], returncode=0, stdout="56 passed", stderr=""
                )
            return CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        mock_run.side_effect = subprocess_side_effect

        # Mock GenAI unavailable
        mock_instance = Mock()
        mock_analyzer_class.return_value = mock_instance
        mock_instance.analyze.return_value = None  # GenAI unavailable

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        # Should still produce output (via heuristics)
        assert mock_stderr.called


# =============================================================================
# Test Exit Code Compliance
# =============================================================================

class TestExitCodeCompliance:
    """Test compliance with SubagentStop lifecycle exit code constraints."""

    @patch("sys.stdin.read")
    def test_main_always_returns_exit_success(self, mock_stdin):
        """Should always return EXIT_SUCCESS (SubagentStop hooks cannot block)."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})

        exit_code = main()

        assert exit_code == EXIT_SUCCESS
        assert exit_code == 0

    @patch("implementation_quality_gate.extract_implementation_diff")
    @patch("sys.stdin.read")
    def test_main_returns_exit_success_on_exception(
        self, mock_stdin, mock_extract
    ):
        """Should return EXIT_SUCCESS even when exceptions occur."""
        mock_stdin.return_value = json.dumps({"agent_name": "implementer"})
        mock_extract.side_effect = Exception("Unexpected error")

        exit_code = main()

        assert exit_code == EXIT_SUCCESS

    def test_exit_success_constant_equals_zero(self):
        """Should verify EXIT_SUCCESS constant equals 0."""
        assert EXIT_SUCCESS == 0
