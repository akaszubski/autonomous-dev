#!/usr/bin/env python3
"""
TDD Tests for Update Plugin CLI (FAILING - Red Phase)

This module contains FAILING tests for update_plugin.py CLI script which provides
interactive command-line interface for plugin updates.

Requirements:
1. Parse CLI arguments (--check-only, --yes, --auto-backup, --verbose, --json)
2. Interactive confirmation prompts before update
3. Display version comparison and update summary
4. Handle user consent (yes/no/cancel)
5. Exit codes: 0 = success, 1 = error, 2 = no update needed
6. JSON output mode for scripting
7. Verbose mode for detailed logging

Test Coverage Target: 90%+ of CLI logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe CLI interface requirements
- Tests should FAIL until update_plugin.py is implemented
- Each test validates ONE CLI requirement

Author: test-master agent
Date: 2025-11-09
Issue: GitHub #50 Phase 2 - Interactive /update-plugin command
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until update_plugin.py is created
from plugins.autonomous_dev.lib.update_plugin import (
    main,
    parse_args,
    confirm_update,
    display_version_comparison,
    display_update_summary,
)
from plugins.autonomous_dev.lib.plugin_updater import UpdateResult
from plugins.autonomous_dev.lib.version_detector import VersionComparison


class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parse_args_defaults(self):
        """Test argument parsing with no arguments.

        REQUIREMENT: CLI must work with no arguments (interactive mode).
        Expected: Default values for all arguments.
        """
        with patch("sys.argv", ["update_plugin.py"]):
            args = parse_args()

            assert args.check_only is False
            assert args.yes is False
            assert args.auto_backup is True  # Default to safe
            assert args.verbose is False
            assert args.json is False
            assert args.project_root is None  # Use cwd

    def test_parse_args_check_only(self):
        """Test --check-only flag parsing.

        REQUIREMENT: Support dry-run mode to check without updating.
        Expected: check_only=True.
        """
        with patch("sys.argv", ["update_plugin.py", "--check-only"]):
            args = parse_args()

            assert args.check_only is True
            assert args.yes is False  # Don't auto-confirm in check mode

    def test_parse_args_yes_flag(self):
        """Test --yes flag for non-interactive mode.

        REQUIREMENT: Support non-interactive updates for automation.
        Expected: yes=True skips confirmation prompts.
        """
        with patch("sys.argv", ["update_plugin.py", "--yes"]):
            args = parse_args()

            assert args.yes is True

    def test_parse_args_no_backup(self):
        """Test --no-backup flag parsing.

        REQUIREMENT: Allow skipping backup for advanced users.
        Expected: auto_backup=False.
        """
        with patch("sys.argv", ["update_plugin.py", "--no-backup"]):
            args = parse_args()

            assert args.auto_backup is False

    def test_parse_args_verbose(self):
        """Test --verbose flag parsing.

        REQUIREMENT: Support verbose output for debugging.
        Expected: verbose=True.
        """
        with patch("sys.argv", ["update_plugin.py", "--verbose"]):
            args = parse_args()

            assert args.verbose is True

    def test_parse_args_json_output(self):
        """Test --json flag for machine-readable output.

        REQUIREMENT: Support JSON output for scripting.
        Expected: json=True.
        """
        with patch("sys.argv", ["update_plugin.py", "--json"]):
            args = parse_args()

            assert args.json is True

    def test_parse_args_custom_project_root(self):
        """Test --project-root argument parsing.

        REQUIREMENT: Support updating projects in different directories.
        Expected: project_root set to custom path.
        """
        custom_path = "/custom/project/path"
        with patch("sys.argv", ["update_plugin.py", "--project-root", custom_path]):
            args = parse_args()

            assert args.project_root == custom_path

    def test_parse_args_combined_flags(self):
        """Test parsing multiple flags together.

        REQUIREMENT: Support combining multiple flags.
        Expected: All flags parsed correctly.
        """
        with patch("sys.argv", [
            "update_plugin.py",
            "--verbose",
            "--yes",
            "--no-backup",
            "--project-root", "/test"
        ]):
            args = parse_args()

            assert args.verbose is True
            assert args.yes is True
            assert args.auto_backup is False
            assert args.project_root == "/test"


class TestConfirmUpdate:
    """Test interactive confirmation prompts."""

    def test_confirm_update_yes_response(self):
        """Test confirmation with 'yes' response.

        REQUIREMENT: Accept 'yes' as confirmation.
        Expected: Returns True.
        """
        with patch("builtins.input", return_value="yes"):
            result = confirm_update(
                current_version="3.7.0",
                new_version="3.8.0"
            )

            assert result is True

    def test_confirm_update_y_response(self):
        """Test confirmation with 'y' response.

        REQUIREMENT: Accept 'y' as shorthand confirmation.
        Expected: Returns True.
        """
        with patch("builtins.input", return_value="y"):
            result = confirm_update(
                current_version="3.7.0",
                new_version="3.8.0"
            )

            assert result is True

    def test_confirm_update_no_response(self):
        """Test confirmation with 'no' response.

        REQUIREMENT: Respect user declining update.
        Expected: Returns False.
        """
        with patch("builtins.input", return_value="no"):
            result = confirm_update(
                current_version="3.7.0",
                new_version="3.8.0"
            )

            assert result is False

    def test_confirm_update_n_response(self):
        """Test confirmation with 'n' response.

        REQUIREMENT: Accept 'n' as shorthand decline.
        Expected: Returns False.
        """
        with patch("builtins.input", return_value="n"):
            result = confirm_update(
                current_version="3.7.0",
                new_version="3.8.0"
            )

            assert result is False

    def test_confirm_update_case_insensitive(self):
        """Test confirmation is case insensitive.

        REQUIREMENT: Accept YES, Yes, yes, etc.
        Expected: Returns True for any case.
        """
        for response in ["YES", "Yes", "Y", "yEs"]:
            with patch("builtins.input", return_value=response):
                result = confirm_update(
                    current_version="3.7.0",
                    new_version="3.8.0"
                )

                assert result is True

    def test_confirm_update_invalid_response_retry(self):
        """Test confirmation handles invalid responses.

        REQUIREMENT: Re-prompt on invalid input.
        Expected: Re-prompts until valid response.
        """
        with patch("builtins.input", side_effect=["maybe", "sure", "yes"]):
            result = confirm_update(
                current_version="3.7.0",
                new_version="3.8.0"
            )

            assert result is True

    def test_confirm_update_displays_version_info(self, capsys):
        """Test confirmation displays version information.

        REQUIREMENT: Show user what update they're confirming.
        Expected: Version info printed before prompt.
        """
        with patch("builtins.input", return_value="no"):
            confirm_update(current_version="3.7.0", new_version="3.8.0")

            captured = capsys.readouterr()
            assert "3.7.0" in captured.out
            assert "3.8.0" in captured.out


class TestDisplayVersionComparison:
    """Test version comparison display."""

    def test_display_version_comparison_upgrade(self, capsys):
        """Test displaying version upgrade information.

        REQUIREMENT: Show clear upgrade message.
        Expected: Output shows upgrade available.
        """
        comparison = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        display_version_comparison(comparison)

        captured = capsys.readouterr()
        assert "upgrade" in captured.out.lower()
        assert "3.7.0" in captured.out
        assert "3.8.0" in captured.out

    def test_display_version_comparison_up_to_date(self, capsys):
        """Test displaying up-to-date status.

        REQUIREMENT: Show clear up-to-date message.
        Expected: Output shows no update needed.
        """
        comparison = VersionComparison(
            project_version="3.8.0",
            marketplace_version="3.8.0",
            is_equal=True,
            project_newer=False,
            marketplace_newer=False,
            status="UP_TO_DATE"
        )

        display_version_comparison(comparison)

        captured = capsys.readouterr()
        assert "up to date" in captured.out.lower() or "up-to-date" in captured.out.lower()
        assert "3.8.0" in captured.out

    def test_display_version_comparison_downgrade(self, capsys):
        """Test displaying downgrade warning.

        REQUIREMENT: Warn user about downgrade risk.
        Expected: Output shows downgrade warning.
        """
        comparison = VersionComparison(
            project_version="3.9.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=True,
            marketplace_newer=False,
            status="DOWNGRADE_RISK"
        )

        display_version_comparison(comparison)

        captured = capsys.readouterr()
        assert "downgrade" in captured.out.lower() or "warning" in captured.out.lower()
        assert "3.9.0" in captured.out
        assert "3.8.0" in captured.out


class TestDisplayUpdateSummary:
    """Test update summary display."""

    def test_display_update_summary_success(self, capsys):
        """Test displaying successful update summary.

        REQUIREMENT: Show clear success message with details.
        Expected: Output shows success and version change.
        """
        result = UpdateResult(
            success=True,
            updated=True,
            message="Plugin updated successfully",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup-123",
            rollback_performed=False,
            details={"files_updated": 5}
        )

        display_update_summary(result)

        captured = capsys.readouterr()
        assert "success" in captured.out.lower()
        assert "3.7.0" in captured.out
        assert "3.8.0" in captured.out
        assert "5" in captured.out  # Files updated

    def test_display_update_summary_no_update(self, capsys):
        """Test displaying no update needed summary.

        REQUIREMENT: Show clear message when no update needed.
        Expected: Output shows up-to-date status.
        """
        result = UpdateResult(
            success=True,
            updated=False,
            message="Plugin is already up to date",
            old_version="3.8.0",
            new_version="3.8.0",
            backup_path=None,
            rollback_performed=False,
            details={}
        )

        display_update_summary(result)

        captured = capsys.readouterr()
        assert "up to date" in captured.out.lower() or "up-to-date" in captured.out.lower()

    def test_display_update_summary_failure_with_rollback(self, capsys):
        """Test displaying failure with rollback summary.

        REQUIREMENT: Show rollback performed when update fails.
        Expected: Output shows failure and rollback.
        """
        result = UpdateResult(
            success=False,
            updated=False,
            message="Update failed, rolled back to 3.7.0",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup-123",
            rollback_performed=True,
            details={"error": "Verification failed"}
        )

        display_update_summary(result)

        captured = capsys.readouterr()
        assert "failed" in captured.out.lower() or "error" in captured.out.lower()
        assert "rolled back" in captured.out.lower() or "rollback" in captured.out.lower()
        assert "3.7.0" in captured.out


class TestMainFunction:
    """Test main() CLI entry point."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        plugin_dir = project_root / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))
        return project_root

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_check_only_mode(self, mock_updater_class, temp_project, capsys):
        """Test main() with --check-only flag.

        REQUIREMENT: Check-only mode shows version without updating.
        Expected: Displays version info, exit code 0, no update performed.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        with patch("sys.argv", ["update_plugin.py", "--check-only", "--project-root", str(temp_project)]):
            exit_code = main()

        assert exit_code == 0
        mock_updater.check_for_updates.assert_called_once()
        mock_updater.update.assert_not_called()  # Should NOT update

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_yes_flag_skips_confirmation(self, mock_updater_class, temp_project):
        """Test main() with --yes flag skips confirmation.

        REQUIREMENT: Non-interactive mode for automation.
        Expected: Update without prompting, exit code 0.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )
        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            details={}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--project-root", str(temp_project)]):
            with patch("builtins.input") as mock_input:
                exit_code = main()

                # Should NOT prompt
                mock_input.assert_not_called()
                assert exit_code == 0
                mock_updater.update.assert_called_once()

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_user_declines_update(self, mock_updater_class, temp_project):
        """Test main() when user declines update.

        REQUIREMENT: Respect user declining update.
        Expected: No update performed, exit code 0.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        with patch("sys.argv", ["update_plugin.py", "--project-root", str(temp_project)]):
            with patch("builtins.input", return_value="no"):
                exit_code = main()

                assert exit_code == 0
                mock_updater.update.assert_not_called()

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_no_update_needed_exit_code(self, mock_updater_class, temp_project):
        """Test main() exit code when no update needed.

        REQUIREMENT: Exit code 2 when already up-to-date.
        Expected: Exit code 2 for scripting detection.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.8.0",
            marketplace_version="3.8.0",
            is_equal=True,
            project_newer=False,
            marketplace_newer=False,
            status="UP_TO_DATE"
        )

        with patch("sys.argv", ["update_plugin.py", "--project-root", str(temp_project)]):
            exit_code = main()

            assert exit_code == 2

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_update_failure_exit_code(self, mock_updater_class, temp_project):
        """Test main() exit code when update fails.

        REQUIREMENT: Exit code 1 on error.
        Expected: Exit code 1 for error detection.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )
        mock_updater.update.return_value = UpdateResult(
            success=False,
            updated=False,
            message="Update failed",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=True,
            details={"error": "Permission denied"}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--project-root", str(temp_project)]):
            exit_code = main()

            assert exit_code == 1

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_json_output_mode(self, mock_updater_class, temp_project, capsys):
        """Test main() with --json flag for machine-readable output.

        REQUIREMENT: JSON output for scripting.
        Expected: Valid JSON output with update details.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )
        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            details={"files_updated": 5}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--json", "--project-root", str(temp_project)]):
            exit_code = main()

            captured = capsys.readouterr()
            output_data = json.loads(captured.out)

            assert output_data["success"] is True
            assert output_data["updated"] is True
            assert output_data["old_version"] == "3.7.0"
            assert output_data["new_version"] == "3.8.0"

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_verbose_mode_logging(self, mock_updater_class, temp_project, capsys):
        """Test main() with --verbose flag shows detailed logging.

        REQUIREMENT: Verbose output for debugging.
        Expected: Detailed progress messages displayed.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )
        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup-123",
            rollback_performed=False,
            details={}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--verbose", "--project-root", str(temp_project)]):
            exit_code = main()

            captured = capsys.readouterr()
            # Should show detailed progress
            assert "checking" in captured.out.lower() or "updating" in captured.out.lower()
            assert "/tmp/backup-123" in captured.out  # Show backup path

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_exception_handling(self, mock_updater_class, temp_project):
        """Test main() handles unexpected exceptions.

        REQUIREMENT: Graceful error handling for unexpected errors.
        Expected: Exit code 1, error message displayed.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater
        mock_updater.check_for_updates.side_effect = Exception("Unexpected error")

        with patch("sys.argv", ["update_plugin.py", "--project-root", str(temp_project)]):
            exit_code = main()

            assert exit_code == 1


# ============================================================================
# Test Hook Activation CLI Integration (Phase 2.5)
# ============================================================================


class TestHookActivationCLI:
    """Test CLI integration for hook activation feature.

    Phase 2.5 - Automatic hook activation in /update-plugin
    """

    def test_parse_args_activate_hooks_flag(self):
        """Test --activate-hooks flag parsing.

        REQUIREMENT: Support explicit hook activation flag.
        Expected: activate_hooks=True when flag present.
        """
        with patch("sys.argv", ["update_plugin.py", "--activate-hooks"]):
            args = parse_args()

            assert args.activate_hooks is True

    def test_parse_args_no_activate_hooks_flag(self):
        """Test --no-activate-hooks flag parsing.

        REQUIREMENT: Support explicit hook activation skip.
        Expected: activate_hooks=False when flag present.
        """
        with patch("sys.argv", ["update_plugin.py", "--no-activate-hooks"]):
            args = parse_args()

            assert args.activate_hooks is False

    def test_parse_args_conflicting_hook_flags(self):
        """Test error when both --activate-hooks and --no-activate-hooks specified.

        REQUIREMENT: Reject conflicting flags.
        Expected: ArgumentError or exit with error message.
        """
        with patch("sys.argv", ["update_plugin.py", "--activate-hooks", "--no-activate-hooks"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_default_hook_activation(self):
        """Test default hook activation behavior when no flags specified.

        REQUIREMENT: Default should be None (let PluginUpdater decide based on first install).
        Expected: activate_hooks=None by default.
        """
        with patch("sys.argv", ["update_plugin.py"]):
            args = parse_args()

            # Default should be None to allow auto-detection
            assert args.activate_hooks is None

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    @patch("plugins.autonomous_dev.lib.update_plugin.prompt_for_hook_activation")
    def test_main_prompts_for_hook_activation_first_install(self, mock_prompt, mock_updater_class, temp_project):
        """Test main() prompts for hook activation on first install.

        REQUIREMENT: Interactive prompt on first install.
        Expected: prompt_for_hook_activation() called when first install detected.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater

        # Mock first install detection
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version=None,
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="FIRST_INSTALL"
        )

        # Mock user says yes to activation
        mock_prompt.return_value = True

        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version=None,
            new_version="3.8.0",
            backup_path=None,
            rollback_performed=False,
            hooks_activated=True,
            details={"hooks_added": 3}
        )

        with patch("sys.argv", ["update_plugin.py", "--project-root", str(temp_project)]):
            exit_code = main()

            # Verify prompt was shown
            mock_prompt.assert_called_once()
            # Verify update called with activate_hooks=True
            mock_updater.update.assert_called_with(activate_hooks=True, auto_backup=True)

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    @patch("plugins.autonomous_dev.lib.update_plugin.prompt_for_hook_activation")
    def test_main_prompts_for_hook_activation_on_update(self, mock_prompt, mock_updater_class, temp_project):
        """Test main() prompts for hook activation on update (not first install).

        REQUIREMENT: Interactive prompt on update.
        Expected: prompt_for_hook_activation() called for update scenario.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater

        # Mock update scenario
        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        # Mock user says no to activation
        mock_prompt.return_value = False

        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            hooks_activated=False,
            details={}
        )

        with patch("sys.argv", ["update_plugin.py", "--project-root", str(temp_project)]):
            exit_code = main()

            # Verify prompt was shown
            mock_prompt.assert_called_once()
            # Verify update called with activate_hooks=False
            mock_updater.update.assert_called_with(activate_hooks=False, auto_backup=True)

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_skips_prompt_when_yes_flag_and_activate_hooks(self, mock_updater_class, temp_project):
        """Test main() skips prompt when --yes and --activate-hooks specified.

        REQUIREMENT: Non-interactive mode with explicit flags.
        Expected: No prompt, activate_hooks=True passed to update().
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater

        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            hooks_activated=True,
            details={"hooks_added": 2}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--activate-hooks", "--project-root", str(temp_project)]):
            exit_code = main()

            # Verify update called with activate_hooks=True
            mock_updater.update.assert_called_with(activate_hooks=True, auto_backup=True)

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_json_output_includes_hooks_activated_status(self, mock_updater_class, temp_project, capsys):
        """Test JSON output includes hooks_activated field.

        REQUIREMENT: Machine-readable output should include hook status.
        Expected: JSON contains hooks_activated and hooks_added fields.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater

        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            hooks_activated=True,
            details={"hooks_added": 5}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--activate-hooks", "--json", "--project-root", str(temp_project)]):
            exit_code = main()

            captured = capsys.readouterr()
            output = json.loads(captured.out)

            # Verify JSON includes hook fields
            assert "hooks_activated" in output
            assert output["hooks_activated"] is True
            assert "hooks_added" in output
            assert output["hooks_added"] == 5

    def test_prompt_for_hook_activation_first_install_auto_yes(self):
        """Test prompt_for_hook_activation() auto-accepts on first install.

        REQUIREMENT: First install should default to activating hooks.
        Expected: Returns True without user input on first install.
        """
        with patch("builtins.input") as mock_input:
            # Should not need input for first install
            result = prompt_for_hook_activation(first_install=True)

            assert result is True
            # Verify input was NOT called (auto-yes)
            mock_input.assert_not_called()

    def test_prompt_for_hook_activation_update_asks_user(self):
        """Test prompt_for_hook_activation() asks user on update.

        REQUIREMENT: Update scenario should prompt user.
        Expected: Returns user's choice based on input.
        """
        with patch("builtins.input", return_value="y"):
            result = prompt_for_hook_activation(first_install=False)

            assert result is True

        with patch("builtins.input", return_value="n"):
            result = prompt_for_hook_activation(first_install=False)

            assert result is False

    def test_prompt_for_hook_activation_handles_invalid_input(self):
        """Test prompt_for_hook_activation() handles invalid user input.

        REQUIREMENT: Handle invalid input gracefully.
        Expected: Re-prompt on invalid input, eventually return choice.
        """
        with patch("builtins.input", side_effect=["invalid", "maybe", "y"]):
            result = prompt_for_hook_activation(first_install=False)

            assert result is True

    @patch("plugins.autonomous_dev.lib.plugin_updater.PluginUpdater")
    def test_main_displays_hook_activation_summary(self, mock_updater_class, temp_project, capsys):
        """Test main() displays hook activation results in summary.

        REQUIREMENT: User should see hook activation results.
        Expected: Summary output mentions hooks activated.
        """
        mock_updater = Mock()
        mock_updater_class.return_value = mock_updater

        mock_updater.check_for_updates.return_value = VersionComparison(
            project_version="3.7.0",
            marketplace_version="3.8.0",
            is_equal=False,
            project_newer=False,
            marketplace_newer=True,
            status="UPGRADE_AVAILABLE"
        )

        mock_updater.update.return_value = UpdateResult(
            success=True,
            updated=True,
            message="Updated",
            old_version="3.7.0",
            new_version="3.8.0",
            backup_path="/tmp/backup",
            rollback_performed=False,
            hooks_activated=True,
            details={"hooks_added": 3}
        )

        with patch("sys.argv", ["update_plugin.py", "--yes", "--activate-hooks", "--project-root", str(temp_project)]):
            exit_code = main()

            captured = capsys.readouterr()
            # Verify output mentions hooks
            assert "hook" in captured.out.lower()
            assert "3" in captured.out or "activated" in captured.out.lower()
