#!/usr/bin/env python3
"""
TDD Tests for Validate Marketplace Version Script (FAILING - Red Phase)

This module contains FAILING tests for validate_marketplace_version.py which will
be used by /health-check command to detect version differences between marketplace
plugin and local project.

Requirements from Planner (GitHub Issue #50):
1. CLI script with --project-root argument
2. Calls detect_version_mismatch() from version_detector.py
3. Formats output for /health-check report integration
4. Exit codes: 0=success, 1=error
5. Security: Path validation and audit logging
6. Non-blocking: Errors don't crash health check

Test Coverage Target: 100% of CLI script logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe version detection requirements
- Tests should FAIL until validate_marketplace_version.py is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-09
Issue: GitHub #50 - Fix Marketplace Update UX
Related: version_detector.py (lib), orphan_file_cleaner.py (lib)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until validate_marketplace_version.py is created
from plugins.autonomous_dev.lib.validate_marketplace_version import (
    validate_marketplace_version,
    format_version_report,
    main,
)


class TestValidateMarketplaceVersionCLI:
    """Test CLI interface for validate_marketplace_version.py script."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create temporary environment with project structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create .claude directory structure
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Create plugins directory
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir()

        # Create autonomous-dev plugin directory
        plugin_dir = plugins_dir / "autonomous-dev"
        plugin_dir.mkdir()

        # Create marketplace plugin directory
        marketplace_dir = claude_dir / "marketplace" / "akaszubski" / "autonomous-dev"
        marketplace_dir.mkdir(parents=True)

        return {
            "project_root": project_root,
            "plugin_dir": plugin_dir,
            "marketplace_dir": marketplace_dir,
        }

    def test_cli_accepts_project_root_argument(self, temp_environment):
        """Test CLI accepts --project-root argument.

        REQUIREMENT: Script must accept project root path via CLI.
        Expected: --project-root argument parsed correctly.
        """
        project_root = temp_environment["project_root"]

        # Create plugin.json files
        plugin_json = temp_environment["plugin_dir"] / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        marketplace_json = temp_environment["marketplace_dir"] / "plugin.json"
        marketplace_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # Mock detect_version_mismatch
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=True,
                marketplace_version="3.8.0",
                project_version="3.7.0",
                message="Upgrade available: 3.7.0 → 3.8.0"
            )

            # Call validate with project_root
            result = validate_marketplace_version(project_root=str(project_root))

            # Verify detect_version_mismatch called with correct path
            mock_detect.assert_called_once()
            call_kwargs = mock_detect.call_args[1]
            assert call_kwargs["project_root"] == str(project_root)

    def test_cli_returns_exit_code_0_on_success(self, temp_environment):
        """Test CLI returns exit code 0 on successful version check.

        REQUIREMENT: Exit codes must indicate success/failure.
        Expected: Exit code 0 when version check succeeds.
        """
        project_root = temp_environment["project_root"]

        # Create plugin.json files
        plugin_json = temp_environment["plugin_dir"] / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        marketplace_json = temp_environment["marketplace_dir"] / "plugin.json"
        marketplace_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        # Mock detect_version_mismatch
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=False,
                marketplace_version="3.8.0",
                project_version="3.8.0",
                message="Version up-to-date: 3.8.0"
            )

            # Mock sys.exit to capture exit code
            with patch('sys.exit') as mock_exit:
                with patch('sys.argv', ['validate_marketplace_version.py', '--project-root', str(project_root)]):
                    main()

                # Should exit with code 0
                mock_exit.assert_called_once_with(0)

    def test_cli_returns_exit_code_1_on_error(self, temp_environment):
        """Test CLI returns exit code 1 on error.

        REQUIREMENT: Exit codes must indicate success/failure.
        Expected: Exit code 1 when version check fails.
        """
        project_root = temp_environment["project_root"]

        # Don't create plugin.json files (will cause error)

        # Mock detect_version_mismatch to raise error
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.side_effect = FileNotFoundError("plugin.json not found")

            # Mock sys.exit to capture exit code
            with patch('sys.exit') as mock_exit:
                with patch('sys.argv', ['validate_marketplace_version.py', '--project-root', str(project_root)]):
                    main()

                # Should exit with code 1
                mock_exit.assert_called_once_with(1)

    def test_cli_requires_project_root_argument(self):
        """Test CLI requires --project-root argument.

        REQUIREMENT: Script must validate required arguments.
        Expected: Error message when --project-root missing.
        """
        # Mock sys.exit to capture exit code
        with patch('sys.exit') as mock_exit:
            with patch('sys.argv', ['validate_marketplace_version.py']):
                main()

            # argparse calls sys.exit(2) for missing required arg
            # Then exception handler may call sys.exit(1)
            # Just verify at least one exit call with error code
            assert mock_exit.called
            # Check that an error exit code was used (not 0)
            exit_codes = [call[0][0] for call in mock_exit.call_args_list]
            assert any(code != 0 for code in exit_codes)


class TestVersionReportFormatting:
    """Test formatting version comparison results for /health-check integration."""

    def test_format_upgrade_available_message(self):
        """Test formatting message when marketplace has newer version.

        REQUIREMENT: Clear messaging for upgrade scenarios.
        Expected: "Marketplace: 3.8.0 | Project: 3.7.0 | Status: Upgrade available"
        """
        comparison = MagicMock(
            is_upgrade=True,
            marketplace_version="3.8.0",
            project_version="3.7.0",
            message="Upgrade available: 3.7.0 → 3.8.0"
        )

        report = format_version_report(comparison)

        assert "3.8.0" in report
        assert "3.7.0" in report
        assert "Upgrade available" in report or "UPGRADE" in report

    def test_format_up_to_date_message(self):
        """Test formatting message when versions match.

        REQUIREMENT: Clear messaging for up-to-date scenarios.
        Expected: "Marketplace: 3.8.0 | Project: 3.8.0 | Status: Up-to-date"
        """
        comparison = MagicMock(
            is_upgrade=False,
            is_downgrade=False,
            marketplace_version="3.8.0",
            project_version="3.8.0",
            message="Version up-to-date: 3.8.0"
        )

        report = format_version_report(comparison)

        assert "3.8.0" in report
        assert "up-to-date" in report.lower() or "UP-TO-DATE" in report

    def test_format_downgrade_detected_message(self):
        """Test formatting message when project has newer version than marketplace.

        REQUIREMENT: Clear messaging for downgrade scenarios.
        Expected: "Marketplace: 3.7.0 | Project: 3.8.0 | Status: Local ahead"
        """
        comparison = MagicMock(
            is_upgrade=False,
            is_downgrade=True,
            marketplace_version="3.7.0",
            project_version="3.8.0",
            message="Downgrade detected: 3.8.0 → 3.7.0"
        )

        report = format_version_report(comparison)

        assert "3.7.0" in report
        assert "3.8.0" in report
        assert "ahead" in report.lower() or "AHEAD" in report or "downgrade" in report.lower()

    def test_format_report_includes_all_version_info(self):
        """Test report includes marketplace version, project version, and status.

        REQUIREMENT: Report must include all relevant version information.
        Expected: Report contains marketplace_version, project_version, status.
        """
        comparison = MagicMock(
            is_upgrade=True,
            marketplace_version="3.9.0",
            project_version="3.7.5",
            message="Upgrade available: 3.7.5 → 3.9.0"
        )

        report = format_version_report(comparison)

        # Must include both versions
        assert "3.9.0" in report
        assert "3.7.5" in report

        # Must include status indicator
        assert any(keyword in report.lower() for keyword in ["upgrade", "update", "available"])

    def test_format_report_for_health_check_integration(self):
        """Test report format is compatible with /health-check output.

        REQUIREMENT: Output must integrate cleanly with health check report.
        Expected: Single line format suitable for health check display.
        """
        comparison = MagicMock(
            is_upgrade=True,
            marketplace_version="3.8.0",
            project_version="3.7.0",
            message="Upgrade available: 3.7.0 → 3.8.0"
        )

        report = format_version_report(comparison)

        # Should be single line (no multi-line output for health check)
        assert "\n" not in report.strip()

        # Should be reasonably short (< 100 chars for clean display)
        assert len(report) < 100


class TestVersionValidationFunction:
    """Test main validate_marketplace_version() function."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create temporary environment with project structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create .claude directory structure
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()

        # Create plugins directory
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir()

        # Create autonomous-dev plugin directory
        plugin_dir = plugins_dir / "autonomous-dev"
        plugin_dir.mkdir()

        # Create marketplace plugin directory
        marketplace_dir = claude_dir / "marketplace" / "akaszubski" / "autonomous-dev"
        marketplace_dir.mkdir(parents=True)

        return {
            "project_root": project_root,
            "plugin_dir": plugin_dir,
            "marketplace_dir": marketplace_dir,
        }

    def test_validate_calls_detect_version_mismatch(self, temp_environment):
        """Test validate_marketplace_version() calls detect_version_mismatch().

        REQUIREMENT: Function must use version_detector library.
        Expected: detect_version_mismatch() called with project_root.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=False,
                marketplace_version="3.8.0",
                project_version="3.8.0",
                message="Version up-to-date"
            )

            result = validate_marketplace_version(project_root=str(project_root))

            # Verify detect_version_mismatch called
            mock_detect.assert_called_once()

    def test_validate_returns_formatted_report(self, temp_environment):
        """Test validate_marketplace_version() returns formatted report string.

        REQUIREMENT: Function must return human-readable report.
        Expected: Returns formatted string with version information.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=True,
                marketplace_version="3.8.0",
                project_version="3.7.0",
                message="Upgrade available"
            )

            result = validate_marketplace_version(project_root=str(project_root))

            # Should return string
            assert isinstance(result, str)

            # Should contain version info
            assert "3.8.0" in result
            assert "3.7.0" in result

    def test_validate_handles_marketplace_not_found(self, temp_environment):
        """Test validate_marketplace_version() handles missing marketplace gracefully.

        REQUIREMENT: Non-blocking error handling for /health-check.
        Expected: Returns error message instead of raising exception.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.side_effect = FileNotFoundError("Marketplace plugin.json not found")

            result = validate_marketplace_version(project_root=str(project_root))

            # Should return error message (not raise exception)
            assert isinstance(result, str)
            assert "error" in result.lower() or "not found" in result.lower()

    def test_validate_handles_project_not_found(self, temp_environment):
        """Test validate_marketplace_version() handles missing project plugin gracefully.

        REQUIREMENT: Non-blocking error handling for /health-check.
        Expected: Returns error message instead of raising exception.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.side_effect = FileNotFoundError("Project plugin.json not found")

            result = validate_marketplace_version(project_root=str(project_root))

            # Should return error message (not raise exception)
            assert isinstance(result, str)
            assert "error" in result.lower() or "not found" in result.lower()


class TestSecurityValidation:
    """Test security requirements for validate_marketplace_version.py."""

    def test_validates_project_root_path(self):
        """Test that project_root path is validated for security.

        REQUIREMENT: Security - path validation (CWE-22).
        Expected: Path traversal attempts rejected.
        """
        # Attempt path traversal
        malicious_path = "/etc/../../../../../../etc/passwd"

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_path') as mock_validate:
            mock_validate.side_effect = ValueError("Path traversal detected")

            with pytest.raises(ValueError, match="Path traversal"):
                validate_marketplace_version(project_root=malicious_path)

            # Verify validate_path was called
            mock_validate.assert_called_once()

    def test_audit_logs_version_check_operation(self, temp_environment):
        """Test that version check operations are audit logged.

        REQUIREMENT: Security - audit logging for version checks.
        Expected: audit_log() called with operation details.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=True,
                marketplace_version="3.8.0",
                project_version="3.7.0",
                message="Upgrade available"
            )

            with patch('plugins.autonomous_dev.lib.validate_marketplace_version.audit_log') as mock_audit:
                result = validate_marketplace_version(project_root=str(project_root))

                # Verify audit log called
                mock_audit.assert_called()

                # Verify audit log includes operation details
                # audit_log is called with positional args: (event_type, status, context)
                # So context dict is at call_args[0][2] (3rd positional arg)
                call_args = mock_audit.call_args[0][2]
                assert call_args["operation"] == "marketplace_version_check"

    def test_validates_project_root_is_absolute_path(self):
        """Test that project_root must be absolute path.

        REQUIREMENT: Security - prevent relative path confusion.
        Expected: Relative paths rejected or converted to absolute.
        """
        relative_path = "../../test_project"

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            # Should either reject relative path or convert to absolute
            with pytest.raises((ValueError, FileNotFoundError)):
                validate_marketplace_version(project_root=relative_path)


class TestErrorHandling:
    """Test error handling requirements for non-blocking health check integration."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create temporary environment with project structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        return {
            "project_root": project_root,
        }

    def test_handles_version_parse_error_gracefully(self, temp_environment):
        """Test handling of version parse errors.

        REQUIREMENT: Non-blocking - parse errors don't crash health check.
        Expected: Returns error message with context.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            # Simulate VersionParseError
            from plugins.autonomous_dev.lib.version_detector import VersionParseError
            mock_detect.side_effect = VersionParseError("Invalid version format: 'v3.8.0-beta'")

            result = validate_marketplace_version(project_root=str(project_root))

            # Should return error message
            assert isinstance(result, str)
            assert "error" in result.lower() or "invalid" in result.lower()

    def test_handles_permission_errors_gracefully(self, temp_environment):
        """Test handling of permission errors.

        REQUIREMENT: Non-blocking - permission errors don't crash health check.
        Expected: Returns error message about permissions.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.side_effect = PermissionError("Permission denied: plugin.json")

            result = validate_marketplace_version(project_root=str(project_root))

            # Should return error message
            assert isinstance(result, str)
            assert "permission" in result.lower() or "error" in result.lower()

    def test_includes_helpful_context_in_error_messages(self, temp_environment):
        """Test that error messages include helpful context.

        REQUIREMENT: Error messages must include context + expected format.
        Expected: Error messages explain what went wrong and what's expected.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.side_effect = FileNotFoundError("plugin.json not found")

            result = validate_marketplace_version(project_root=str(project_root))

            # Should include context
            assert "plugin.json" in result or "not found" in result.lower()

            # Should suggest next steps
            assert any(keyword in result.lower() for keyword in ["install", "marketplace", "missing"])


class TestCLIArgumentParsing:
    """Test CLI argument parsing for validate_marketplace_version.py script."""

    def test_cli_accepts_verbose_flag(self, temp_environment):
        """Test CLI accepts optional --verbose flag.

        REQUIREMENT: CLI should support verbose output for debugging.
        Expected: --verbose flag enables detailed output.
        """
        project_root = temp_environment["project_root"]

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=True,
                marketplace_version="3.8.0",
                project_version="3.7.0",
                message="Upgrade available"
            )

            with patch('sys.exit') as mock_exit:
                with patch('sys.argv', ['validate_marketplace_version.py', '--project-root', str(project_root), '--verbose']):
                    main()

                # Should complete successfully
                mock_exit.assert_called_once_with(0)

    def test_cli_accepts_json_output_flag(self):
        """Test CLI accepts optional --json flag for machine-readable output.

        REQUIREMENT: CLI should support JSON output for programmatic use.
        Expected: --json flag outputs JSON format.
        """
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.detect_version_mismatch') as mock_detect:
            mock_detect.return_value = MagicMock(
                is_upgrade=True,
                marketplace_version="3.8.0",
                project_version="3.7.0",
                message="Upgrade available"
            )

            with patch('sys.exit') as mock_exit:
                with patch('sys.argv', ['validate_marketplace_version.py', '--project-root', '/tmp/test', '--json']):
                    with patch('builtins.print') as mock_print:
                        main()

                        # Should print JSON output
                        output = str(mock_print.call_args)
                        # Note: Actual JSON validation happens in implementation
                        assert mock_print.called

    def test_cli_shows_help_with_help_flag(self):
        """Test CLI shows help message with --help flag.

        REQUIREMENT: CLI should provide usage documentation.
        Expected: --help flag displays usage information.
        """
        with patch('sys.exit') as mock_exit:
            with patch('sys.argv', ['validate_marketplace_version.py', '--help']):
                with pytest.raises(SystemExit):
                    main()


@pytest.fixture
def temp_environment(tmp_path):
    """Create temporary environment with project structure.

    Global fixture for all test classes.
    """
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create .claude directory structure
    claude_dir = project_root / ".claude"
    claude_dir.mkdir()

    # Create plugins directory
    plugins_dir = claude_dir / "plugins"
    plugins_dir.mkdir()

    # Create autonomous-dev plugin directory
    plugin_dir = plugins_dir / "autonomous-dev"
    plugin_dir.mkdir()

    # Create marketplace plugin directory
    marketplace_dir = claude_dir / "marketplace" / "akaszubski" / "autonomous-dev"
    marketplace_dir.mkdir(parents=True)

    return {
        "project_root": project_root,
        "plugin_dir": plugin_dir,
        "marketplace_dir": marketplace_dir,
    }
