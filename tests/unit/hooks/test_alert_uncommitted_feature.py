#!/usr/bin/env python3
"""
TDD Tests for Uncommitted Feature Alert Hook (FAILING - Red Phase)

This module contains FAILING tests for alert_uncommitted_feature.py hook which
warns about uncommitted changes exceeding threshold.

Requirements:
1. Return EXIT_WARNING when 100+ lines uncommitted
2. Return EXIT_SUCCESS when <100 lines uncommitted
3. Return EXIT_SUCCESS when no uncommitted changes
4. Parse git diff --stat output correctly
5. Handle git not available gracefully
6. Support custom threshold via environment variable
7. Use standardized exit codes from hook_exit_codes
8. Respect lifecycle constraints (PreSubagent can warn)

Test Coverage Target: 95%+ of hook logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe hook behavior requirements
- Tests should FAIL until alert_uncommitted_feature.py is implemented
- Each test validates ONE hook requirement

Hook Type: PreSubagent
Trigger: Before subagent starts
Condition: Uncommitted changes exceed threshold
Action: Warn user but allow continuation

Author: test-master agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from subprocess import CalledProcessError, TimeoutExpired

import pytest

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

# Import exit codes
from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

# This import will FAIL until alert_uncommitted_feature.py is created
from alert_uncommitted_feature import (
    get_uncommitted_changes_count,
    parse_git_diff_stat,
    should_alert_uncommitted,
    format_alert_message,
    run_hook,
    main,
)


class TestGetUncommittedChangesCount:
    """Test get_uncommitted_changes_count() function."""

    @patch('subprocess.run')
    def test_count_with_changes(self, mock_run):
        """Test counting uncommitted changes with modifications.

        REQUIREMENT: Count uncommitted lines from git diff.
        Expected: Returns total insertions + deletions.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" example.py | 50 +++++++++++++++++++++++\n utils.py | 30 ---------------",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        assert count == 80  # 50 + 30

    @patch('subprocess.run')
    def test_count_no_changes(self, mock_run):
        """Test counting with no uncommitted changes.

        REQUIREMENT: Return 0 when no uncommitted changes.
        Expected: Returns 0.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        assert count == 0

    @patch('subprocess.run')
    def test_count_multiple_files(self, mock_run):
        """Test counting across multiple files.

        REQUIREMENT: Sum changes across all files.
        Expected: Returns total from all files.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
 file1.py | 20 +++++++++++++++++
 file2.py | 15 +++++++++----
 file3.py | 30 +++++++++++++++----------
 file4.py | 40 --------------------------
""",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        # 20 + 15 + 30 + 40 = 105
        assert count == 105

    @patch('subprocess.run')
    def test_git_not_available(self, mock_run):
        """Test handling git not available.

        REQUIREMENT: Handle git not available gracefully.
        Expected: Returns 0, doesn't crash.
        """
        mock_run.side_effect = FileNotFoundError("git not found")

        count = get_uncommitted_changes_count()

        assert count == 0

    @patch('subprocess.run')
    def test_git_error(self, mock_run):
        """Test handling git command error.

        REQUIREMENT: Handle git errors gracefully.
        Expected: Returns 0, doesn't crash.
        """
        mock_run.side_effect = CalledProcessError(
            returncode=128,
            cmd="git diff",
            output="fatal: not a git repository"
        )

        count = get_uncommitted_changes_count()

        assert count == 0

    @patch('subprocess.run')
    def test_git_diff_stat_called_correctly(self, mock_run):
        """Test git diff --stat command is called correctly.

        REQUIREMENT: Use git diff --stat for counting.
        Expected: git diff --stat --cached HEAD called.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        get_uncommitted_changes_count()

        args = mock_run.call_args[0][0]
        assert args[0] == 'git'
        assert 'diff' in args
        assert '--stat' in args


class TestParseGitDiffStat:
    """Test parse_git_diff_stat() function."""

    def test_parse_single_file_additions(self):
        """Test parsing single file with additions.

        REQUIREMENT: Parse git diff --stat output.
        Expected: Extracts addition count.
        """
        output = " example.py | 50 ++++++++++++++++++++++"

        count = parse_git_diff_stat(output)

        assert count == 50

    def test_parse_single_file_deletions(self):
        """Test parsing single file with deletions.

        REQUIREMENT: Parse deletions from git diff --stat.
        Expected: Extracts deletion count.
        """
        output = " example.py | 30 ---------------"

        count = parse_git_diff_stat(output)

        assert count == 30

    def test_parse_single_file_mixed_changes(self):
        """Test parsing single file with additions and deletions.

        REQUIREMENT: Parse mixed changes.
        Expected: Extracts total count (additions + deletions).
        """
        output = " example.py | 45 +++++++++++++++----------"

        count = parse_git_diff_stat(output)

        assert count == 45

    def test_parse_multiple_files(self):
        """Test parsing multiple files.

        REQUIREMENT: Sum changes across multiple files.
        Expected: Returns total from all files.
        """
        output = """
 file1.py | 20 +++++++++++++++++
 file2.py | 15 +++++++++----
 file3.py | 30 --------------------------
"""

        count = parse_git_diff_stat(output)

        assert count == 65  # 20 + 15 + 30

    def test_parse_empty_output(self):
        """Test parsing empty git output.

        REQUIREMENT: Handle empty output gracefully.
        Expected: Returns 0.
        """
        output = ""

        count = parse_git_diff_stat(output)

        assert count == 0

    def test_parse_summary_line_ignored(self):
        """Test summary line is ignored.

        REQUIREMENT: Ignore summary line from git diff --stat.
        Expected: Only count file lines, not summary.
        """
        output = """
 file1.py | 20 +++++++++++++++++
 file2.py | 15 +++++++++----
 2 files changed, 35 insertions(+)
"""

        count = parse_git_diff_stat(output)

        # Should be 35 (20 + 15), not affected by summary line
        assert count == 35

    def test_parse_binary_files_ignored(self):
        """Test binary files are handled.

        REQUIREMENT: Handle binary files in git diff --stat.
        Expected: Binary files don't crash parser.
        """
        output = """
 file1.py | 20 +++++++++++++++++
 binary.bin | Bin 0 -> 1024 bytes
 file2.py | 15 +++++++++----
"""

        count = parse_git_diff_stat(output)

        # Should count text files only
        assert count == 35  # 20 + 15

    def test_parse_malformed_line(self):
        """Test handling malformed git output.

        REQUIREMENT: Handle malformed output gracefully.
        Expected: Skips malformed lines, doesn't crash.
        """
        output = """
 file1.py | 20 +++++++++++++++++
 malformed line without proper format
 file2.py | 15 +++++++++----
"""

        count = parse_git_diff_stat(output)

        # Should count valid lines only
        assert count == 35  # 20 + 15


class TestShouldAlertUncommitted:
    """Test should_alert_uncommitted() decision logic."""

    def test_alert_when_exceeds_default_threshold(self):
        """Test alert when changes exceed default threshold (100 lines).

        REQUIREMENT: Alert when 100+ lines uncommitted.
        Expected: Returns True for 100+ lines.
        """
        assert should_alert_uncommitted(100) is True
        assert should_alert_uncommitted(150) is True
        assert should_alert_uncommitted(1000) is True

    def test_no_alert_when_below_default_threshold(self):
        """Test no alert when changes below default threshold.

        REQUIREMENT: No alert when <100 lines uncommitted.
        Expected: Returns False for <100 lines.
        """
        assert should_alert_uncommitted(0) is False
        assert should_alert_uncommitted(50) is False
        assert should_alert_uncommitted(99) is False

    def test_alert_with_custom_threshold(self):
        """Test alert with custom threshold.

        REQUIREMENT: Support custom threshold.
        Expected: Returns True when exceeds custom threshold.
        """
        assert should_alert_uncommitted(150, threshold=200) is False
        assert should_alert_uncommitted(200, threshold=200) is True
        assert should_alert_uncommitted(250, threshold=200) is True

    def test_edge_case_exact_threshold(self):
        """Test exact threshold value.

        REQUIREMENT: Threshold is inclusive.
        Expected: Returns True when equals threshold.
        """
        assert should_alert_uncommitted(100, threshold=100) is True


class TestFormatAlertMessage:
    """Test format_alert_message() function."""

    def test_format_message_basic(self):
        """Test basic alert message formatting.

        REQUIREMENT: Format clear alert message.
        Expected: Message includes line count and guidance.
        """
        message = format_alert_message(150)

        assert "150" in message
        assert "uncommitted" in message.lower() or "changes" in message.lower()

    def test_format_message_includes_threshold(self):
        """Test message includes threshold information.

        REQUIREMENT: Message explains threshold.
        Expected: Message mentions threshold value.
        """
        message = format_alert_message(150, threshold=100)

        assert "100" in message or "threshold" in message.lower()

    def test_format_message_includes_git_hint(self):
        """Test message includes git commit hint.

        REQUIREMENT: Message guides user to action.
        Expected: Message suggests git commit.
        """
        message = format_alert_message(150)

        assert "commit" in message.lower() or "git" in message.lower()


class TestRunHook:
    """Test run_hook() main hook logic."""

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    def test_hook_returns_warning_when_exceeds_threshold(self, mock_count):
        """Test hook returns EXIT_WARNING when exceeds threshold.

        REQUIREMENT: Return EXIT_WARNING when 100+ lines uncommitted.
        Expected: Returns EXIT_WARNING (1), prints alert.
        """
        mock_count.return_value = 150

        exit_code = run_hook()

        assert exit_code == EXIT_WARNING

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    def test_hook_returns_success_when_below_threshold(self, mock_count):
        """Test hook returns EXIT_SUCCESS when below threshold.

        REQUIREMENT: Return EXIT_SUCCESS when <100 lines uncommitted.
        Expected: Returns EXIT_SUCCESS (0).
        """
        mock_count.return_value = 50

        exit_code = run_hook()

        assert exit_code == EXIT_SUCCESS

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    def test_hook_returns_success_when_no_changes(self, mock_count):
        """Test hook returns EXIT_SUCCESS when no changes.

        REQUIREMENT: Return EXIT_SUCCESS when no uncommitted changes.
        Expected: Returns EXIT_SUCCESS (0).
        """
        mock_count.return_value = 0

        exit_code = run_hook()

        assert exit_code == EXIT_SUCCESS

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    @patch.dict(os.environ, {'UNCOMMITTED_THRESHOLD': '200'})
    def test_hook_respects_env_var_threshold(self, mock_count):
        """Test hook respects UNCOMMITTED_THRESHOLD env var.

        REQUIREMENT: Support custom threshold via environment variable.
        Expected: Uses threshold from env var.
        """
        mock_count.return_value = 150

        # 150 is below 200 threshold, should succeed
        exit_code = run_hook()

        assert exit_code == EXIT_SUCCESS

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    @patch.dict(os.environ, {'UNCOMMITTED_THRESHOLD': '100'})
    def test_hook_warns_with_env_var_threshold(self, mock_count):
        """Test hook warns when exceeds env var threshold.

        REQUIREMENT: Alert based on env var threshold.
        Expected: Returns EXIT_WARNING when exceeds env threshold.
        """
        mock_count.return_value = 150

        # 150 exceeds 100 threshold, should warn
        exit_code = run_hook()

        assert exit_code == EXIT_WARNING

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    @patch('sys.stdout')
    def test_hook_prints_alert_message(self, mock_stdout, mock_count):
        """Test hook prints alert message to stdout.

        REQUIREMENT: Display alert to user.
        Expected: Prints formatted alert message.
        """
        mock_count.return_value = 150

        run_hook()

        # Should have printed something
        assert mock_stdout.write.called or print.__called__

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    def test_hook_handles_git_error_gracefully(self, mock_count):
        """Test hook handles git errors gracefully.

        REQUIREMENT: Handle git errors gracefully.
        Expected: Returns EXIT_SUCCESS, doesn't crash.
        """
        mock_count.side_effect = Exception("Git error")

        exit_code = run_hook()

        # Should not crash, should succeed (can't verify without git)
        assert exit_code == EXIT_SUCCESS


class TestMainEntry:
    """Test main() entry point."""

    @patch('alert_uncommitted_feature.run_hook')
    def test_main_calls_run_hook(self, mock_run_hook):
        """Test main() calls run_hook().

        REQUIREMENT: main() is proper entry point.
        Expected: Calls run_hook() and exits with its code.
        """
        mock_run_hook.return_value = EXIT_SUCCESS

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_SUCCESS
        mock_run_hook.assert_called_once()

    @patch('alert_uncommitted_feature.run_hook')
    def test_main_exits_with_warning_code(self, mock_run_hook):
        """Test main() exits with EXIT_WARNING.

        REQUIREMENT: main() propagates exit codes.
        Expected: Exits with EXIT_WARNING when hook returns it.
        """
        mock_run_hook.return_value = EXIT_WARNING

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == EXIT_WARNING


class TestLifecycleConstraints:
    """Test lifecycle constraints for PreSubagent hooks."""

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    def test_hook_never_returns_exit_block(self, mock_count):
        """Test hook never returns EXIT_BLOCK (lifecycle constraint).

        REQUIREMENT: PreSubagent hooks can warn but not block.
        Expected: Never returns EXIT_BLOCK (2), only EXIT_SUCCESS or EXIT_WARNING.
        """
        # Try various counts
        test_counts = [0, 50, 100, 200, 1000]

        for count in test_counts:
            mock_count.return_value = count
            exit_code = run_hook()

            # Should only return EXIT_SUCCESS or EXIT_WARNING, never EXIT_BLOCK
            assert exit_code in (EXIT_SUCCESS, EXIT_WARNING)
            assert exit_code != EXIT_BLOCK


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('subprocess.run')
    def test_very_large_change_count(self, mock_run):
        """Test handling very large uncommitted changes.

        REQUIREMENT: Handle large numbers gracefully.
        Expected: Counts large numbers correctly, doesn't overflow.
        """
        # Simulate very large file
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" huge_file.py | 50000 +++++++++++++++++++++++++++",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        assert count == 50000

    @patch('subprocess.run')
    def test_unicode_in_filenames(self, mock_run):
        """Test handling unicode characters in filenames.

        REQUIREMENT: Handle unicode filenames gracefully.
        Expected: Parses counts correctly even with unicode names.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" 文件.py | 20 +++++++++++++++++",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        assert count == 20

    @patch('subprocess.run')
    def test_spaces_in_filenames(self, mock_run):
        """Test handling spaces in filenames.

        REQUIREMENT: Handle spaces in filenames gracefully.
        Expected: Parses counts correctly with spaces.
        """
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" my file.py | 20 +++++++++++++++++",
            stderr=""
        )

        count = get_uncommitted_changes_count()

        assert count == 20

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    @patch.dict(os.environ, {'UNCOMMITTED_THRESHOLD': 'invalid'})
    def test_invalid_threshold_env_var(self, mock_count):
        """Test handling invalid UNCOMMITTED_THRESHOLD env var.

        REQUIREMENT: Handle invalid env var gracefully.
        Expected: Falls back to default threshold (100).
        """
        mock_count.return_value = 150

        # Invalid threshold should fall back to default (100)
        exit_code = run_hook()

        # 150 exceeds default 100, should warn
        assert exit_code == EXIT_WARNING

    @patch('alert_uncommitted_feature.get_uncommitted_changes_count')
    @patch.dict(os.environ, {'DISABLE_UNCOMMITTED_ALERT': 'true'})
    def test_disable_alert_env_var(self, mock_count):
        """Test disabling alert via env var.

        REQUIREMENT: Support disabling alert.
        Expected: Always returns EXIT_SUCCESS when disabled.
        """
        mock_count.return_value = 1000

        exit_code = run_hook()

        # Should succeed even with large changes when disabled
        assert exit_code == EXIT_SUCCESS

    @patch('subprocess.run')
    def test_timeout_on_git_command(self, mock_run):
        """Test handling git command timeout.

        REQUIREMENT: Handle timeout gracefully.
        Expected: Returns 0 (can't verify), doesn't crash.
        """
        mock_run.side_effect = TimeoutExpired(cmd='git diff --stat', timeout=5)

        count = get_uncommitted_changes_count()

        assert count == 0  # Treat timeout as no changes

    @patch('subprocess.run')
    def test_staged_and_unstaged_changes(self, mock_run):
        """Test counting both staged and unstaged changes.

        REQUIREMENT: Count all uncommitted changes (staged + unstaged).
        Expected: git diff called for both staged and unstaged.
        """
        # First call: staged changes
        # Second call: unstaged changes
        mock_run.side_effect = [
            Mock(returncode=0, stdout=" file1.py | 50 +++++++++++++++++", stderr=""),
            Mock(returncode=0, stdout=" file2.py | 30 ++++++++++++", stderr=""),
        ]

        count = get_uncommitted_changes_count()

        # Should count both staged and unstaged
        # Implementation might call git diff twice or use different command
        assert count >= 50  # At least one set of changes
