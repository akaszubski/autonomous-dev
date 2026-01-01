"""
Unit tests for /worktree command interface.

Tests the command-line interface for git worktree management:
- Argument parsing (5 modes: list, review, merge, discard, status)
- List mode (default, shows all worktrees)
- Status mode (detailed info for specific worktree)
- Review mode (interactive diff review with approve/reject)
- Merge mode (merge worktree to target branch)
- Discard mode (delete worktree with confirmation)

Note: worktree_manager.py library is already tested (58 tests).
These tests focus on command interface only.

TDD Phase: RED - All tests should fail initially
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add lib directory to path for imports
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

lib_path = project_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))


class TestArgumentParsing:
    """Test command-line argument parsing for /worktree command."""

    def test_default_mode_is_list(self):
        """Test that no arguments defaults to --list mode."""
        from worktree_command import parse_args

        args = parse_args([])
        assert args.mode == 'list'
        assert args.feature is None

    def test_list_flag_explicit(self):
        """Test explicit --list flag parsing."""
        from worktree_command import parse_args

        args = parse_args(['--list'])
        assert args.mode == 'list'
        assert args.feature is None

    def test_review_requires_feature_name(self):
        """Test --review flag requires feature name argument."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--review'])

    def test_merge_requires_feature_name(self):
        """Test --merge flag requires feature name argument."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--merge'])

    def test_discard_requires_feature_name(self):
        """Test --discard flag requires feature name argument."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--discard'])

    def test_status_requires_feature_name(self):
        """Test --status flag requires feature name argument."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--status'])

    def test_invalid_flag_rejected(self):
        """Test that invalid flags are rejected."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--invalid-flag'])

    def test_review_with_feature_name(self):
        """Test --review with feature name parses correctly."""
        from worktree_command import parse_args

        args = parse_args(['--review', 'my-feature'])
        assert args.mode == 'review'
        assert args.feature == 'my-feature'

    def test_merge_with_feature_name(self):
        """Test --merge with feature name parses correctly."""
        from worktree_command import parse_args

        args = parse_args(['--merge', 'my-feature'])
        assert args.mode == 'merge'
        assert args.feature == 'my-feature'

    def test_discard_with_feature_name(self):
        """Test --discard with feature name parses correctly."""
        from worktree_command import parse_args

        args = parse_args(['--discard', 'my-feature'])
        assert args.mode == 'discard'
        assert args.feature == 'my-feature'

    def test_status_with_feature_name(self):
        """Test --status with feature name parses correctly."""
        from worktree_command import parse_args

        args = parse_args(['--status', 'my-feature'])
        assert args.mode == 'status'
        assert args.feature == 'my-feature'


class TestListMode:
    """Test --list mode (default mode, shows all worktrees)."""

    @patch('worktree_command.worktree_manager.list_worktrees')
    def test_list_empty_worktrees(self, mock_list):
        """Test list mode with no worktrees."""
        from worktree_command import main

        mock_list.return_value = []

        result = main(['--list'])

        assert result == 0
        mock_list.assert_called_once()

    @patch('worktree_command.worktree_manager.list_worktrees')
    def test_list_single_worktree(self, mock_list):
        """Test list mode with single worktree."""
        from worktree_command import main

        mock_list.return_value = [{
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'clean'
        }]

        result = main(['--list'])

        assert result == 0
        mock_list.assert_called_once()

    @patch('worktree_command.worktree_manager.list_worktrees')
    def test_list_multiple_worktrees(self, mock_list):
        """Test list mode with multiple worktrees."""
        from worktree_command import main

        mock_list.return_value = [
            {
                'feature': 'feature-1',
                'path': '/tmp/worktrees/feature-1',
                'branch': 'feature/feature-1',
                'status': 'clean'
            },
            {
                'feature': 'feature-2',
                'path': '/tmp/worktrees/feature-2',
                'branch': 'feature/feature-2',
                'status': 'dirty'
            },
            {
                'feature': 'feature-3',
                'path': '/tmp/worktrees/feature-3',
                'branch': 'feature/feature-3',
                'status': 'clean'
            }
        ]

        result = main(['--list'])

        assert result == 0
        mock_list.assert_called_once()

    @patch('worktree_command.worktree_manager.list_worktrees')
    @patch('builtins.print')
    def test_list_shows_status_column(self, mock_print, mock_list):
        """Test list mode includes status column."""
        from worktree_command import main

        mock_list.return_value = [{
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'dirty'
        }]

        main(['--list'])

        # Verify status is shown in output
        printed_output = ''.join([str(call[0]) for call in mock_print.call_args_list])
        assert 'dirty' in printed_output.lower() or 'uncommitted' in printed_output.lower()


class TestStatusMode:
    """Test --status mode (show detailed info for specific worktree)."""

    @patch('worktree_command.worktree_manager.get_worktree_status')
    def test_status_shows_details(self, mock_status):
        """Test status mode shows worktree details."""
        from worktree_command import main

        mock_status.return_value = {
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'clean',
            'commits_ahead': 3,
            'commits_behind': 0,
            'target_branch': 'master'
        }

        result = main(['--status', 'my-feature'])

        assert result == 0
        mock_status.assert_called_once_with('my-feature')

    @patch('worktree_command.worktree_manager.get_worktree_status')
    def test_status_worktree_not_found(self, mock_status):
        """Test status mode with non-existent worktree."""
        from worktree_command import main

        mock_status.side_effect = FileNotFoundError("Worktree not found")

        result = main(['--status', 'nonexistent'])

        assert result == 1
        mock_status.assert_called_once_with('nonexistent')

    @patch('worktree_command.worktree_manager.get_worktree_status')
    @patch('builtins.print')
    def test_status_shows_commits_ahead(self, mock_print, mock_status):
        """Test status mode shows commits ahead/behind."""
        from worktree_command import main

        mock_status.return_value = {
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'clean',
            'commits_ahead': 5,
            'commits_behind': 2,
            'target_branch': 'master'
        }

        main(['--status', 'my-feature'])

        # Verify commits ahead/behind are shown
        printed_output = ''.join([str(call[0]) for call in mock_print.call_args_list])
        assert '5' in printed_output  # commits ahead
        assert '2' in printed_output  # commits behind


class TestReviewMode:
    """Test --review mode (interactive diff review with approve/reject)."""

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.AskUserQuestion')
    def test_review_shows_diff(self, mock_ask, mock_diff):
        """Test review mode shows git diff."""
        from worktree_command import main

        mock_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
        mock_ask.return_value = 'reject'  # Don't merge

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once_with('my-feature')
        mock_ask.assert_called_once()

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.worktree_manager.merge_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_review_approve_triggers_merge(self, mock_ask, mock_merge, mock_diff):
        """Test review mode with approve triggers merge."""
        from worktree_command import main

        mock_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
        mock_ask.return_value = 'approve'
        mock_merge.return_value = {'success': True, 'conflicts': []}

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once_with('my-feature')
        mock_ask.assert_called_once()
        mock_merge.assert_called_once_with('my-feature')

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.AskUserQuestion')
    def test_review_reject_exits_cleanly(self, mock_ask, mock_diff):
        """Test review mode with reject exits without merge."""
        from worktree_command import main

        mock_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
        mock_ask.return_value = 'reject'

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once_with('my-feature')
        mock_ask.assert_called_once()

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    def test_review_worktree_not_found(self, mock_diff):
        """Test review mode with non-existent worktree."""
        from worktree_command import main

        mock_diff.side_effect = FileNotFoundError("Worktree not found")

        result = main(['--review', 'nonexistent'])

        assert result == 1
        mock_diff.assert_called_once_with('nonexistent')


class TestMergeMode:
    """Test --merge mode (merge worktree to target branch)."""

    @patch('worktree_command.worktree_manager.merge_worktree')
    def test_merge_success(self, mock_merge):
        """Test successful merge."""
        from worktree_command import main

        mock_merge.return_value = {
            'success': True,
            'conflicts': [],
            'target_branch': 'master'
        }

        result = main(['--merge', 'my-feature'])

        assert result == 0
        mock_merge.assert_called_once_with('my-feature')

    @patch('worktree_command.worktree_manager.merge_worktree')
    @patch('builtins.print')
    def test_merge_with_conflicts_shows_files(self, mock_print, mock_merge):
        """Test merge with conflicts shows conflicting files."""
        from worktree_command import main

        mock_merge.return_value = {
            'success': False,
            'conflicts': ['file1.py', 'file2.py'],
            'target_branch': 'master'
        }

        result = main(['--merge', 'my-feature'])

        assert result == 1
        mock_merge.assert_called_once_with('my-feature')

        # Verify conflict files are shown
        printed_output = ''.join([str(call[0]) for call in mock_print.call_args_list])
        assert 'file1.py' in printed_output
        assert 'file2.py' in printed_output

    @patch('worktree_command.worktree_manager.merge_worktree')
    def test_merge_worktree_not_found(self, mock_merge):
        """Test merge mode with non-existent worktree."""
        from worktree_command import main

        mock_merge.side_effect = FileNotFoundError("Worktree not found")

        result = main(['--merge', 'nonexistent'])

        assert result == 1
        mock_merge.assert_called_once_with('nonexistent')

    @patch('worktree_command.worktree_manager.merge_worktree')
    @patch('worktree_command.os.getenv')
    def test_merge_respects_auto_git_enabled(self, mock_getenv, mock_merge):
        """Test merge mode respects AUTO_GIT_ENABLED environment variable."""
        from worktree_command import main

        mock_getenv.return_value = 'false'
        mock_merge.return_value = {
            'success': True,
            'conflicts': [],
            'target_branch': 'master'
        }

        result = main(['--merge', 'my-feature'])

        assert result == 0
        mock_merge.assert_called_once_with('my-feature')


class TestDiscardMode:
    """Test --discard mode (delete worktree with confirmation)."""

    @patch('worktree_command.worktree_manager.discard_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_discard_requires_confirmation(self, mock_ask, mock_discard):
        """Test discard mode requires user confirmation."""
        from worktree_command import main

        mock_ask.return_value = 'yes'
        mock_discard.return_value = {'success': True}

        result = main(['--discard', 'my-feature'])

        assert result == 0
        mock_ask.assert_called_once()
        mock_discard.assert_called_once_with('my-feature')

    @patch('worktree_command.AskUserQuestion')
    def test_discard_cancelled_on_no(self, mock_ask):
        """Test discard mode cancelled when user says no."""
        from worktree_command import main

        mock_ask.return_value = 'no'

        result = main(['--discard', 'my-feature'])

        assert result == 0
        mock_ask.assert_called_once()

    @patch('worktree_command.worktree_manager.discard_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_discard_proceeds_on_yes(self, mock_ask, mock_discard):
        """Test discard mode proceeds when user confirms."""
        from worktree_command import main

        mock_ask.return_value = 'yes'
        mock_discard.return_value = {'success': True}

        result = main(['--discard', 'my-feature'])

        assert result == 0
        mock_ask.assert_called_once()
        mock_discard.assert_called_once_with('my-feature')

    @patch('worktree_command.worktree_manager.discard_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_discard_worktree_not_found(self, mock_ask, mock_discard):
        """Test discard mode with non-existent worktree."""
        from worktree_command import main

        mock_ask.return_value = 'yes'
        mock_discard.side_effect = FileNotFoundError("Worktree not found")

        result = main(['--discard', 'nonexistent'])

        assert result == 1
        mock_ask.assert_called_once()
        mock_discard.assert_called_once_with('nonexistent')

    @patch('worktree_command.worktree_manager.get_worktree_status')
    @patch('worktree_command.worktree_manager.discard_worktree')
    @patch('worktree_command.AskUserQuestion')
    @patch('builtins.print')
    def test_discard_with_uncommitted_changes(self, mock_print, mock_ask, mock_discard, mock_status):
        """Test discard mode warns about uncommitted changes."""
        from worktree_command import main

        mock_status.return_value = {
            'feature': 'my-feature',
            'status': 'dirty',
            'uncommitted_files': ['file1.py', 'file2.py']
        }
        mock_ask.return_value = 'yes'
        mock_discard.return_value = {'success': True}

        result = main(['--discard', 'my-feature'])

        assert result == 0
        mock_status.assert_called_once_with('my-feature')
        mock_ask.assert_called_once()

        # Verify warning about uncommitted changes
        printed_output = ''.join([str(call[0]) for call in mock_print.call_args_list])
        assert 'uncommitted' in printed_output.lower() or 'unsaved' in printed_output.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_modes_rejected(self):
        """Test that specifying multiple modes is rejected."""
        from worktree_command import parse_args

        with pytest.raises(SystemExit):
            parse_args(['--list', '--review', 'my-feature'])

    @patch('worktree_command.worktree_manager.list_worktrees')
    def test_list_mode_handles_errors_gracefully(self, mock_list):
        """Test list mode handles errors gracefully."""
        from worktree_command import main

        mock_list.side_effect = Exception("Git command failed")

        result = main(['--list'])

        assert result == 1

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.AskUserQuestion')
    def test_review_mode_handles_empty_diff(self, mock_ask, mock_diff):
        """Test review mode with empty diff (no changes)."""
        from worktree_command import main

        mock_diff.return_value = ""
        mock_ask.return_value = 'reject'

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once_with('my-feature')

    @patch('worktree_command.worktree_manager.merge_worktree')
    def test_merge_mode_handles_git_errors(self, mock_merge):
        """Test merge mode handles git errors gracefully."""
        from worktree_command import main

        mock_merge.side_effect = Exception("Git merge failed")

        result = main(['--merge', 'my-feature'])

        assert result == 1

    def test_feature_name_with_special_characters(self):
        """Test feature names with special characters are handled."""
        from worktree_command import parse_args

        args = parse_args(['--status', 'feature/my-feature-123'])
        assert args.feature == 'feature/my-feature-123'

    def test_feature_name_with_spaces_rejected(self):
        """Test feature names with spaces are rejected."""
        from worktree_command import parse_args

        # Should either reject or handle gracefully
        args = parse_args(['--status', 'my feature'])
        # Implementation should validate and reject invalid feature names


class TestIntegration:
    """Integration tests for command workflows."""

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.worktree_manager.merge_worktree')
    @patch('worktree_command.worktree_manager.discard_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_review_approve_merge_workflow(self, mock_ask, mock_discard, mock_merge, mock_diff):
        """Test complete review → approve → merge workflow."""
        from worktree_command import main

        mock_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
        mock_ask.return_value = 'approve'
        mock_merge.return_value = {
            'success': True,
            'conflicts': [],
            'target_branch': 'master'
        }

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once()
        mock_merge.assert_called_once()
        mock_discard.assert_not_called()

    @patch('worktree_command.worktree_manager.get_worktree_diff')
    @patch('worktree_command.worktree_manager.merge_worktree')
    @patch('worktree_command.AskUserQuestion')
    def test_review_reject_no_merge_workflow(self, mock_ask, mock_merge, mock_diff):
        """Test complete review → reject → no merge workflow."""
        from worktree_command import main

        mock_diff.return_value = "diff --git a/file.py b/file.py\n+new line"
        mock_ask.return_value = 'reject'

        result = main(['--review', 'my-feature'])

        assert result == 0
        mock_diff.assert_called_once()
        mock_merge.assert_not_called()

    @patch('worktree_command.worktree_manager.list_worktrees')
    @patch('worktree_command.worktree_manager.get_worktree_status')
    def test_list_then_status_workflow(self, mock_status, mock_list):
        """Test list worktrees → check status workflow."""
        from worktree_command import main

        mock_list.return_value = [{
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'clean'
        }]

        # First list
        result1 = main(['--list'])
        assert result1 == 0

        # Then check status
        mock_status.return_value = {
            'feature': 'my-feature',
            'path': '/tmp/worktrees/my-feature',
            'branch': 'feature/my-feature',
            'status': 'clean',
            'commits_ahead': 3,
            'commits_behind': 0
        }

        result2 = main(['--status', 'my-feature'])
        assert result2 == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
