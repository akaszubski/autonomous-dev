#!/usr/bin/env python3
"""
TDD Tests for Sync Mode Detector

This module contains tests for sync_mode_detector.py which provides
intelligent context detection for the unified /sync command.

Requirements:
1. Auto-detect sync mode based on context (plugin-dev → PLUGIN_DEV, otherwise → GITHUB)
2. Parse command-line flags (--github, --env, --marketplace, --plugin-dev, --all)
3. Validate paths using security_utils.py
4. Prevent flag conflicts (e.g., --env AND --marketplace together)
5. Default to GITHUB mode when no plugin-dev context detected (user-friendly update)

Test Coverage Target: 100% of detection logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe behavior requirements
- Tests should FAIL until sync_mode_detector.py is implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #44 - Unified /sync command consolidation
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until sync_mode_detector.py is created
from plugins.autonomous_dev.lib.sync_mode_detector import (
    SyncModeDetector,
    SyncMode,
    SyncModeError,
    detect_sync_mode,
    parse_sync_flags,
)


class TestSyncModeEnum:
    """Test SyncMode enum values exist and are correct."""

    def test_sync_mode_enum_values(self):
        """Verify all expected sync modes are defined.

        REQUIREMENT: SyncMode enum must support all sync types.
        Expected: ENVIRONMENT, MARKETPLACE, PLUGIN_DEV, ALL modes exist.
        """
        assert hasattr(SyncMode, 'ENVIRONMENT')
        assert hasattr(SyncMode, 'MARKETPLACE')
        assert hasattr(SyncMode, 'PLUGIN_DEV')
        assert hasattr(SyncMode, 'ALL')

    def test_sync_mode_enum_unique_values(self):
        """Verify each sync mode has a unique value.

        REQUIREMENT: Enum values must be distinguishable.
        Expected: No duplicate values in enum.
        """
        modes = [
            SyncMode.ENVIRONMENT,
            SyncMode.MARKETPLACE,
            SyncMode.PLUGIN_DEV,
            SyncMode.ALL
        ]
        assert len(modes) == len(set(modes))


class TestContextDetection:
    """Test automatic context detection based on file system state."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        return project_root

    def test_detect_plugin_dev_context_when_plugin_dir_exists(self, temp_project):
        """Test detection when plugins/autonomous-dev/ directory exists.

        REQUIREMENT: Auto-detect plugin development mode.
        Expected: Returns SyncMode.PLUGIN_DEV when plugin directory present.
        """
        # Create plugin directory structure
        plugin_dir = temp_project / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{"version": "3.6.0"}')

        detector = SyncModeDetector(str(temp_project))
        mode = detector.detect_mode()

        assert mode == SyncMode.PLUGIN_DEV

    def test_detect_github_when_claude_dir_exists_but_not_plugin_dev(self, temp_project):
        """Test detection when .claude/ directory exists but not plugin dir.

        REQUIREMENT: Default to GITHUB mode for users (not in autonomous-dev repo).
        Expected: Returns SyncMode.GITHUB even when .claude/ directory present.
        """
        # Create .claude directory
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("# Project")

        detector = SyncModeDetector(str(temp_project))
        mode = detector.detect_mode()

        # Should return GITHUB (default for users), not ENVIRONMENT
        assert mode == SyncMode.GITHUB

    def test_marketplace_flag_still_works(self, temp_project):
        """Test that --marketplace flag can still be used explicitly.

        REQUIREMENT: Allow explicit marketplace sync via flag.
        Expected: Returns SyncMode.MARKETPLACE when --marketplace flag used.
        """
        mode = parse_sync_flags(['--marketplace'])
        assert mode == SyncMode.MARKETPLACE

    def test_default_to_github_when_no_plugin_dev_context(self, temp_project):
        """Test default to GITHUB mode when not in plugin-dev context.

        REQUIREMENT: User-friendly default for update workflow.
        Expected: Returns SyncMode.GITHUB as default (fetch from GitHub).
        """
        # Empty project directory (no plugins/autonomous-dev/)
        detector = SyncModeDetector(str(temp_project))
        mode = detector.detect_mode()

        # Should default to GITHUB for easy updates
        assert mode == SyncMode.GITHUB

    def test_plugin_dev_takes_precedence_over_environment(self, temp_project):
        """Test priority when both plugin dir and .claude dir exist.

        REQUIREMENT: Plugin development mode has highest precedence.
        Expected: Returns PLUGIN_DEV even when .claude/ exists.
        """
        # Create both directories
        plugin_dir = temp_project / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text('{}')

        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()

        detector = SyncModeDetector(str(temp_project))
        mode = detector.detect_mode()

        assert mode == SyncMode.PLUGIN_DEV


class TestFlagParsing:
    """Test command-line flag parsing for mode overrides."""

    def test_parse_github_flag(self):
        """Test --github flag explicitly sets GitHub mode.

        REQUIREMENT: Allow explicit GitHub sync via flag.
        Expected: parse_sync_flags(['--github']) returns SyncMode.GITHUB.
        """
        mode = parse_sync_flags(['--github'])
        assert mode == SyncMode.GITHUB

    def test_parse_env_flag(self):
        """Test --env flag overrides auto-detection.

        REQUIREMENT: Allow explicit environment sync via flag.
        Expected: parse_sync_flags(['--env']) returns SyncMode.ENVIRONMENT.
        """
        mode = parse_sync_flags(['--env'])
        assert mode == SyncMode.ENVIRONMENT

    def test_parse_marketplace_flag(self):
        """Test --marketplace flag overrides auto-detection.

        REQUIREMENT: Allow explicit marketplace sync via flag.
        Expected: parse_sync_flags(['--marketplace']) returns SyncMode.MARKETPLACE.
        """
        mode = parse_sync_flags(['--marketplace'])
        assert mode == SyncMode.MARKETPLACE

    def test_parse_plugin_dev_flag(self):
        """Test --plugin-dev flag overrides auto-detection.

        REQUIREMENT: Allow explicit plugin-dev sync via flag.
        Expected: parse_sync_flags(['--plugin-dev']) returns SyncMode.PLUGIN_DEV.
        """
        mode = parse_sync_flags(['--plugin-dev'])
        assert mode == SyncMode.PLUGIN_DEV

    def test_parse_all_flag(self):
        """Test --all flag enables all sync modes.

        REQUIREMENT: Allow comprehensive sync of all modes.
        Expected: parse_sync_flags(['--all']) returns SyncMode.ALL.
        """
        mode = parse_sync_flags(['--all'])
        assert mode == SyncMode.ALL

    def test_no_flags_returns_none(self):
        """Test empty flags list returns None (triggers auto-detection).

        REQUIREMENT: No flags means use auto-detection.
        Expected: parse_sync_flags([]) returns None.
        """
        mode = parse_sync_flags([])
        assert mode is None

    def test_conflicting_flags_raise_error(self):
        """Test that conflicting flags (--env + --marketplace) raise error.

        REQUIREMENT: Prevent ambiguous flag combinations.
        Expected: SyncModeError raised when multiple mode flags provided.
        """
        with pytest.raises(SyncModeError) as exc_info:
            parse_sync_flags(['--env', '--marketplace'])

        assert 'conflicting' in str(exc_info.value).lower()
        assert '--env' in str(exc_info.value)
        assert '--marketplace' in str(exc_info.value)

    def test_all_flag_conflicts_with_specific_flags(self):
        """Test that --all cannot be combined with specific mode flags.

        REQUIREMENT: --all is mutually exclusive with other flags.
        Expected: SyncModeError when --all used with --env, --marketplace, etc.
        """
        with pytest.raises(SyncModeError) as exc_info:
            parse_sync_flags(['--all', '--env'])

        assert '--all' in str(exc_info.value).lower()
        assert 'cannot be combined' in str(exc_info.value).lower()

    def test_unknown_flag_raises_error(self):
        """Test that unknown flags are rejected.

        REQUIREMENT: Only valid flags accepted.
        Expected: SyncModeError for unrecognized flags.
        """
        with pytest.raises(SyncModeError) as exc_info:
            parse_sync_flags(['--invalid-flag'])

        assert 'unknown flag' in str(exc_info.value).lower()
        assert '--invalid-flag' in str(exc_info.value)

    def test_flag_parsing_case_sensitive(self):
        """Test that flag parsing is case-sensitive.

        REQUIREMENT: Flags must match exactly.
        Expected: --ENV (uppercase) is not recognized.
        """
        with pytest.raises(SyncModeError):
            parse_sync_flags(['--ENV'])


class TestSecurityValidation:
    """Test path validation using security_utils.py integration."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for security testing."""
        project_root = tmp_path / "secure_project"
        project_root.mkdir()
        return project_root

    def test_path_validation_called_on_init(self, temp_project):
        """Test that path validation occurs during detector initialization.

        SECURITY: All paths must be validated before use.
        Expected: security_utils.validate_path() called during __init__.
        """
        with patch('plugins.autonomous_dev.lib.sync_mode_detector.validate_path') as mock_validate:
            mock_validate.return_value = temp_project.resolve()

            detector = SyncModeDetector(str(temp_project))

            mock_validate.assert_called_once()
            # Verify path argument was passed
            call_args = mock_validate.call_args[0]
            assert str(temp_project) in str(call_args[0])

    def test_path_traversal_blocked_during_detection(self, temp_project):
        """Test that path traversal attempts are blocked.

        SECURITY: Reject ../../etc/passwd style paths.
        Expected: SyncModeError raised for invalid paths.
        """
        malicious_path = temp_project / ".." / ".." / "etc" / "passwd"

        with pytest.raises(SyncModeError) as exc_info:
            SyncModeDetector(str(malicious_path))

        assert 'invalid path' in str(exc_info.value).lower()

    def test_symlink_detection_during_validation(self, temp_project):
        """Test that symlinks outside project root are rejected.

        SECURITY: Prevent symlink-based escapes.
        Expected: SyncModeError when symlink points outside whitelist.
        """
        # Create symlink pointing outside project
        symlink_path = temp_project / "link_to_etc"
        etc_path = Path("/etc")

        if etc_path.exists():  # Only test on systems with /etc
            try:
                symlink_path.symlink_to(etc_path)

                with pytest.raises(SyncModeError) as exc_info:
                    SyncModeDetector(str(symlink_path))

                assert 'symlink' in str(exc_info.value).lower()
            finally:
                if symlink_path.exists():
                    symlink_path.unlink()

    def test_audit_logging_on_detection(self, temp_project):
        """Test that detection events are logged to audit log.

        SECURITY: All detection operations must be auditable.
        Expected: audit_log() called with detection details.
        """
        with patch('plugins.autonomous_dev.lib.sync_mode_detector.audit_log') as mock_audit:
            detector = SyncModeDetector(str(temp_project))
            mode = detector.detect_mode()

            # Verify audit log was called
            mock_audit.assert_called()
            # Check that mode detection was logged
            logged_calls = [str(call) for call in mock_audit.call_args_list]
            assert any('detect' in str(call).lower() for call in logged_calls)


class TestDetectorIntegration:
    """Test SyncModeDetector class integration scenarios."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project for integration testing."""
        project_root = tmp_path / "integration_test"
        project_root.mkdir()
        return project_root

    def test_detector_with_explicit_mode_override(self, temp_project):
        """Test that explicit mode parameter overrides auto-detection.

        REQUIREMENT: Allow programmatic mode override.
        Expected: Detector respects explicit mode parameter.
        """
        # Create plugin dir to trigger auto-detection
        plugin_dir = temp_project / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # But override with explicit mode
        detector = SyncModeDetector(str(temp_project), explicit_mode=SyncMode.ENVIRONMENT)
        mode = detector.detect_mode()

        # Should return explicit mode, not auto-detected PLUGIN_DEV
        assert mode == SyncMode.ENVIRONMENT

    def test_detector_caches_detection_result(self, temp_project):
        """Test that detection result is cached for performance.

        REQUIREMENT: Detection should run once, then cache result.
        Expected: Multiple detect_mode() calls return same result without re-scanning.
        """
        detector = SyncModeDetector(str(temp_project))

        # Mock the internal detection method
        with patch.object(detector, '_scan_filesystem', return_value=SyncMode.ENVIRONMENT) as mock_scan:
            # First call
            mode1 = detector.detect_mode()
            # Second call
            mode2 = detector.detect_mode()

            # Should only scan once
            assert mock_scan.call_count == 1
            assert mode1 == mode2

    def test_detector_reset_cache(self, temp_project):
        """Test that cache can be reset to force re-detection.

        REQUIREMENT: Allow cache invalidation for dynamic environments.
        Expected: reset_cache() forces new detection on next detect_mode() call.
        """
        detector = SyncModeDetector(str(temp_project))

        # Initial detection (no plugins dir = GITHUB default)
        mode1 = detector.detect_mode()

        # Create plugin dir
        plugin_dir = temp_project / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Reset cache
        detector.reset_cache()

        # Should detect new mode (PLUGIN_DEV)
        mode2 = detector.detect_mode()

        assert mode1 == SyncMode.GITHUB  # Default for users
        assert mode2 == SyncMode.PLUGIN_DEV  # After plugin dir created

    def test_detector_get_detection_reason(self, temp_project):
        """Test that detector provides human-readable detection reason.

        REQUIREMENT: Explain why mode was selected for user visibility.
        Expected: get_detection_reason() returns clear explanation.
        """
        # Empty project - should default to GITHUB
        detector = SyncModeDetector(str(temp_project))
        mode = detector.detect_mode()
        reason = detector.get_detection_reason()

        assert mode == SyncMode.GITHUB
        assert 'github' in reason.lower() or 'default' in reason.lower()


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_detect_sync_mode_convenience_function(self, tmp_path):
        """Test that detect_sync_mode() is a convenient wrapper.

        REQUIREMENT: Provide simple API for common use case.
        Expected: detect_sync_mode(path) returns GITHUB mode by default.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()

        # Create .claude dir (doesn't matter - defaults to GITHUB for users)
        (project_dir / ".claude").mkdir()

        mode = detect_sync_mode(str(project_dir))

        # Default is now GITHUB for user-friendly updates
        assert mode == SyncMode.GITHUB

    def test_detect_sync_mode_with_flags(self, tmp_path):
        """Test detect_sync_mode() with flag parsing integration.

        REQUIREMENT: Combine detection and flag parsing in one call.
        Expected: detect_sync_mode(path, flags=['--env']) respects flags.
        """
        project_dir = tmp_path / "test"
        project_dir.mkdir()

        # Create plugin dir (would auto-detect as PLUGIN_DEV)
        plugin_dir = project_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # But --env flag should override
        mode = detect_sync_mode(str(project_dir), flags=['--env'])

        assert mode == SyncMode.ENVIRONMENT

    def test_get_all_sync_modes_helper(self):
        """Test helper function to get list of all sync modes.

        REQUIREMENT: Provide programmatic access to all modes.
        Expected: get_all_sync_modes() returns list of all SyncMode values.
        """
        from plugins.autonomous_dev.lib.sync_mode_detector import get_all_sync_modes

        modes = get_all_sync_modes()

        assert SyncMode.GITHUB in modes  # New default mode
        assert SyncMode.ENVIRONMENT in modes
        assert SyncMode.MARKETPLACE in modes
        assert SyncMode.PLUGIN_DEV in modes
        assert SyncMode.ALL in modes
        assert len(modes) == 5  # Now includes GITHUB


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_nonexistent_path_raises_error(self):
        """Test that nonexistent paths are rejected.

        REQUIREMENT: Path must exist before detection.
        Expected: SyncModeError for paths that don't exist or are outside allowed locations.
        """
        fake_path = "/nonexistent/path/12345"

        with pytest.raises(SyncModeError) as exc_info:
            SyncModeDetector(fake_path)

        # Error can be "does not exist" or "outside allowed locations" (security validation)
        error_msg = str(exc_info.value).lower()
        assert 'does not exist' in error_msg or 'outside allowed' in error_msg or 'invalid path' in error_msg

    def test_file_instead_of_directory_raises_error(self, tmp_path):
        """Test that file paths are rejected (must be directory).

        REQUIREMENT: Project path must be a directory.
        Expected: SyncModeError when path points to file.
        """
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        with pytest.raises(SyncModeError) as exc_info:
            SyncModeDetector(str(file_path))

        assert 'must be a directory' in str(exc_info.value).lower()

    def test_permission_denied_handled_gracefully(self, tmp_path):
        """Test graceful handling when directory is not readable.

        REQUIREMENT: Clear error message for permission issues.
        Expected: SyncModeError with helpful message about permissions.
        """
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir(mode=0o000)  # No permissions

        try:
            with pytest.raises(SyncModeError) as exc_info:
                detector = SyncModeDetector(str(restricted_dir))
                detector.detect_mode()

            assert 'permission' in str(exc_info.value).lower()
        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    def test_empty_flags_list_handled_correctly(self):
        """Test that empty flags list doesn't cause errors.

        REQUIREMENT: Handle empty flags gracefully.
        Expected: parse_sync_flags([]) returns None without error.
        """
        mode = parse_sync_flags([])
        assert mode is None

    def test_none_flags_handled_correctly(self):
        """Test that None flags argument doesn't cause errors.

        REQUIREMENT: Handle None flags gracefully.
        Expected: parse_sync_flags(None) returns None without error.
        """
        mode = parse_sync_flags(None)
        assert mode is None
