#!/usr/bin/env python3
"""
TDD Tests for Hook Activator (FAILING - Red Phase)

This module contains FAILING tests for hook_activator.py which will provide
automatic hook activation during plugin updates.

Requirements:
1. Detect first install vs update (check for existing settings.json)
2. Read and parse existing settings.json
3. Merge new hooks with existing settings (preserve customizations)
4. Atomic write with tempfile + rename pattern
5. Validate settings structure before write
6. Create .claude directory if missing
7. Handle edge cases (malformed JSON, missing files, permissions)
8. Security: Path validation, audit logging, proper permissions

Test Coverage Target: 20+ tests (95%+ coverage)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe hook activation requirements
- Tests should FAIL until hook_activator.py is implemented
- Each test validates ONE activation requirement

Author: test-master agent
Date: 2025-11-09
Issue: GitHub #50 Phase 2.5 - Automatic hook activation in /update-plugin
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until hook_activator.py is created
from plugins.autonomous_dev.lib.hook_activator import (
    HookActivator,
    ActivationResult,
    ActivationError,
    SettingsValidationError,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project root directory."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    return project_root


@pytest.fixture
def temp_claude_dir(temp_project_root):
    """Create .claude directory in temporary project."""
    claude_dir = temp_project_root / ".claude"
    claude_dir.mkdir()
    return claude_dir


@pytest.fixture
def sample_settings():
    """Sample settings.json content for testing."""
    return {
        "hooks": {
            "UserPromptSubmit": ["display_project_context.py"],
            "SubagentStop": ["log_agent_completion.py"]
        },
        "custom_setting": "value"
    }


@pytest.fixture
def new_hooks():
    """New hooks to merge during activation."""
    return {
        "hooks": {
            "UserPromptSubmit": [
                "display_project_context.py",
                "enforce_command_limit.py"
            ],
            "SubagentStop": [
                "log_agent_completion.py",
                "auto_update_project_progress.py"
            ],
            "PrePush": ["auto_test.py"]
        }
    }


@pytest.fixture
def mock_security_utils():
    """Mock security_utils for testing."""
    with patch("plugins.autonomous_dev.lib.hook_activator.security_utils") as mock:
        # Default: validation passes
        mock.validate_path.return_value = None
        mock.audit_log.return_value = None
        yield mock


# ============================================================================
# Test ActivationResult Dataclass
# ============================================================================


class TestActivationResultDataclass:
    """Test ActivationResult dataclass creation and attributes."""

    def test_activation_result_success_instantiation(self):
        """Test creating ActivationResult for successful activation.

        REQUIREMENT: ActivationResult must capture success status and details.
        Expected: ActivationResult with activated=True, hook counts, settings path.
        """
        result = ActivationResult(
            activated=True,
            first_install=True,
            message="Successfully activated 3 hooks",
            hooks_added=3,
            settings_path="/path/to/settings.json",
            details={"hooks": ["auto_test.py", "auto_format.py"]}
        )

        assert result.activated is True
        assert result.first_install is True
        assert result.message == "Successfully activated 3 hooks"
        assert result.hooks_added == 3
        assert result.settings_path == "/path/to/settings.json"
        assert "hooks" in result.details

    def test_activation_result_no_activation(self):
        """Test creating ActivationResult when no activation performed.

        REQUIREMENT: ActivationResult must differentiate between activated and skipped.
        Expected: ActivationResult with activated=False.
        """
        result = ActivationResult(
            activated=False,
            first_install=False,
            message="Hooks already configured",
            hooks_added=0,
            settings_path="/path/to/settings.json",
            details={}
        )

        assert result.activated is False
        assert result.first_install is False
        assert result.hooks_added == 0

    def test_activation_result_summary_property(self):
        """Test ActivationResult.summary property generates readable output.

        REQUIREMENT: Summary must include activation status and hook count.
        Expected: Multi-line summary with all details.
        """
        result = ActivationResult(
            activated=True,
            first_install=False,
            message="Updated hook configuration",
            hooks_added=2,
            settings_path="/test/settings.json",
            details={"merged_hooks": True}
        )

        summary = result.summary
        assert "Updated hook configuration" in summary
        assert "2" in summary  # hooks_added
        assert "/test/settings.json" in summary


# ============================================================================
# Test HookActivator Initialization
# ============================================================================


class TestHookActivatorInitialization:
    """Test HookActivator initialization and path validation."""

    def test_init_with_valid_path(self, temp_project_root, mock_security_utils):
        """Test initialization with valid project root path.

        REQUIREMENT: HookActivator must validate project root on init.
        Expected: Successful initialization, paths set correctly.
        """
        activator = HookActivator(project_root=temp_project_root)

        assert activator.project_root == temp_project_root
        assert activator.claude_dir == temp_project_root / ".claude"
        assert activator.settings_path == temp_project_root / ".claude" / "settings.json"

        # Verify security validation was called
        mock_security_utils.validate_path.assert_called()

    def test_init_with_invalid_path(self, mock_security_utils):
        """Test initialization with invalid project root path.

        REQUIREMENT: Invalid paths must be rejected during initialization.
        Expected: ValueError raised with clear error message.
        """
        # Mock validation to raise error
        mock_security_utils.validate_path.side_effect = ValueError(
            "Invalid path: /invalid/path"
        )

        with pytest.raises(ValueError, match="Invalid path"):
            HookActivator(project_root="/invalid/path")

    def test_init_with_path_traversal_attempt(self, mock_security_utils):
        """Test initialization rejects path traversal attempts.

        REQUIREMENT: Security - prevent path traversal (CWE-22).
        Expected: ValueError raised for path traversal.
        """
        # Mock validation to reject path traversal
        mock_security_utils.validate_path.side_effect = ValueError(
            "Path traversal detected"
        )

        with pytest.raises(ValueError, match="Path traversal"):
            HookActivator(project_root="/tmp/../etc/passwd")

    def test_init_creates_paths_from_string(self, temp_project_root, mock_security_utils):
        """Test initialization converts string paths to Path objects.

        REQUIREMENT: Support both string and Path inputs.
        Expected: Internal paths are Path objects.
        """
        activator = HookActivator(project_root=str(temp_project_root))

        assert isinstance(activator.project_root, Path)
        assert isinstance(activator.claude_dir, Path)
        assert isinstance(activator.settings_path, Path)


# ============================================================================
# Test First Install Detection
# ============================================================================


class TestFirstInstallDetection:
    """Test detection of first install vs update scenario."""

    def test_is_first_install_missing_settings(self, temp_project_root, mock_security_utils):
        """Test first install detection when settings.json doesn't exist.

        REQUIREMENT: Detect first install by checking for settings.json.
        Expected: is_first_install() returns True.
        """
        activator = HookActivator(project_root=temp_project_root)

        # settings.json doesn't exist yet
        assert activator.is_first_install() is True

    def test_is_first_install_existing_settings(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test first install detection when settings.json exists.

        REQUIREMENT: Detect update scenario by finding existing settings.json.
        Expected: is_first_install() returns False.
        """
        # Create existing settings.json
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        activator = HookActivator(project_root=temp_project_root)

        assert activator.is_first_install() is False

    def test_is_first_install_missing_claude_dir(self, temp_project_root, mock_security_utils):
        """Test first install detection when .claude directory missing.

        REQUIREMENT: Missing .claude directory indicates first install.
        Expected: is_first_install() returns True.
        """
        # .claude directory doesn't exist
        activator = HookActivator(project_root=temp_project_root)

        assert activator.is_first_install() is True


# ============================================================================
# Test Settings Read and Parse
# ============================================================================


class TestSettingsReadParse:
    """Test reading and parsing existing settings.json."""

    def test_read_existing_settings_valid_json(self, temp_claude_dir, temp_project_root, sample_settings, mock_security_utils):
        """Test reading valid existing settings.json.

        REQUIREMENT: Parse existing settings.json correctly.
        Expected: Returns dict with settings content.
        """
        # Create settings.json with valid content
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps(sample_settings))

        activator = HookActivator(project_root=temp_project_root)
        existing = activator._read_existing_settings()

        assert existing == sample_settings
        assert "hooks" in existing
        assert "custom_setting" in existing

    def test_read_existing_settings_missing_file(self, temp_project_root, mock_security_utils):
        """Test reading settings when file doesn't exist.

        REQUIREMENT: Handle missing settings.json gracefully.
        Expected: Returns empty dict with default hooks structure.
        """
        activator = HookActivator(project_root=temp_project_root)
        existing = activator._read_existing_settings()

        assert existing == {"hooks": {}}

    def test_read_existing_settings_malformed_json(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test reading settings with malformed JSON.

        REQUIREMENT: Handle JSON parse errors gracefully.
        Expected: Raises SettingsValidationError with helpful message.
        """
        # Create settings.json with malformed JSON
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text("{invalid json")

        activator = HookActivator(project_root=temp_project_root)

        with pytest.raises(SettingsValidationError, match="malformed JSON"):
            activator._read_existing_settings()

    def test_read_existing_settings_empty_file(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test reading empty settings.json.

        REQUIREMENT: Handle empty file gracefully.
        Expected: Returns default hooks structure.
        """
        # Create empty settings.json
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text("")

        activator = HookActivator(project_root=temp_project_root)
        existing = activator._read_existing_settings()

        assert existing == {"hooks": {}}

    def test_read_existing_settings_missing_hooks_key(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test reading settings without 'hooks' key.

        REQUIREMENT: Handle missing hooks key by adding default.
        Expected: Returns settings with empty hooks added.
        """
        # Create settings.json without hooks key
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps({"custom": "value"}))

        activator = HookActivator(project_root=temp_project_root)
        existing = activator._read_existing_settings()

        assert "hooks" in existing
        assert existing["hooks"] == {}
        assert existing["custom"] == "value"

    def test_read_existing_settings_permission_denied(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test reading settings when permission denied.

        REQUIREMENT: Handle permission errors gracefully.
        Expected: Raises ActivationError with clear message.
        """
        # Create settings.json with no read permissions
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))
        settings_path.chmod(0o000)

        activator = HookActivator(project_root=temp_project_root)

        try:
            with pytest.raises(ActivationError, match="Permission denied"):
                activator._read_existing_settings()
        finally:
            # Cleanup: restore permissions for cleanup
            settings_path.chmod(0o644)


# ============================================================================
# Test Settings Merge Logic
# ============================================================================


class TestSettingsMerge:
    """Test merging new hooks with existing settings."""

    def test_merge_settings_first_install(self, new_hooks, mock_security_utils):
        """Test merging hooks on first install (no existing settings).

        REQUIREMENT: On first install, use new hooks entirely.
        Expected: Merged settings contain all new hooks.
        """
        activator = HookActivator(project_root="/tmp/test")
        existing = {"hooks": {}}

        merged = activator._merge_settings(existing, new_hooks)

        assert merged["hooks"] == new_hooks["hooks"]
        assert "UserPromptSubmit" in merged["hooks"]
        assert "SubagentStop" in merged["hooks"]
        assert "PrePush" in merged["hooks"]

    def test_merge_settings_preserve_custom_settings(self, sample_settings, new_hooks, mock_security_utils):
        """Test merging preserves custom settings not related to hooks.

        REQUIREMENT: Preserve user customizations during merge.
        Expected: custom_setting preserved, hooks merged.
        """
        activator = HookActivator(project_root="/tmp/test")

        merged = activator._merge_settings(sample_settings, new_hooks)

        assert merged["custom_setting"] == "value"
        assert "hooks" in merged

    def test_merge_settings_add_new_hook_to_existing_lifecycle(self, sample_settings, new_hooks, mock_security_utils):
        """Test merging adds new hooks to existing lifecycle event.

        REQUIREMENT: Merge should add new hooks without removing existing ones.
        Expected: UserPromptSubmit has both old and new hooks.
        """
        activator = HookActivator(project_root="/tmp/test")

        merged = activator._merge_settings(sample_settings, new_hooks)

        user_prompt_hooks = merged["hooks"]["UserPromptSubmit"]
        assert "display_project_context.py" in user_prompt_hooks  # Existing
        assert "enforce_command_limit.py" in user_prompt_hooks  # New

    def test_merge_settings_add_new_lifecycle_event(self, sample_settings, new_hooks, mock_security_utils):
        """Test merging adds new lifecycle event not in existing settings.

        REQUIREMENT: Support adding new lifecycle events.
        Expected: PrePush event added with its hooks.
        """
        activator = HookActivator(project_root="/tmp/test")

        merged = activator._merge_settings(sample_settings, new_hooks)

        assert "PrePush" in merged["hooks"]
        assert "auto_test.py" in merged["hooks"]["PrePush"]

    def test_merge_settings_avoid_duplicate_hooks(self, sample_settings, mock_security_utils):
        """Test merging doesn't create duplicate hooks in same lifecycle.

        REQUIREMENT: Prevent duplicate hook entries.
        Expected: Each hook appears only once per lifecycle event.
        """
        activator = HookActivator(project_root="/tmp/test")

        # New hooks with duplicates
        new_with_dupes = {
            "hooks": {
                "UserPromptSubmit": [
                    "display_project_context.py",  # Already exists
                    "new_hook.py"
                ]
            }
        }

        merged = activator._merge_settings(sample_settings, new_with_dupes)

        user_prompt_hooks = merged["hooks"]["UserPromptSubmit"]
        # Count occurrences
        count = user_prompt_hooks.count("display_project_context.py")
        assert count == 1  # No duplicates

    def test_merge_settings_empty_new_hooks(self, sample_settings, mock_security_utils):
        """Test merging with empty new hooks.

        REQUIREMENT: Handle empty new hooks gracefully.
        Expected: Existing settings unchanged.
        """
        activator = HookActivator(project_root="/tmp/test")
        new_empty = {"hooks": {}}

        merged = activator._merge_settings(sample_settings, new_empty)

        assert merged == sample_settings


# ============================================================================
# Test Settings Validation
# ============================================================================


class TestSettingsValidation:
    """Test settings structure validation before write."""

    def test_validate_settings_valid_structure(self, new_hooks, mock_security_utils):
        """Test validation passes for valid settings structure.

        REQUIREMENT: Validate settings structure before write.
        Expected: No exception raised for valid settings.
        """
        activator = HookActivator(project_root="/tmp/test")

        # Should not raise
        activator._validate_settings(new_hooks)

    def test_validate_settings_missing_hooks_key(self, mock_security_utils):
        """Test validation fails when 'hooks' key missing.

        REQUIREMENT: Settings must have 'hooks' key.
        Expected: SettingsValidationError raised.
        """
        activator = HookActivator(project_root="/tmp/test")
        invalid = {"custom": "value"}

        with pytest.raises(SettingsValidationError, match="missing 'hooks' key"):
            activator._validate_settings(invalid)

    def test_validate_settings_hooks_not_dict(self, mock_security_utils):
        """Test validation fails when 'hooks' is not a dict.

        REQUIREMENT: 'hooks' value must be a dictionary.
        Expected: SettingsValidationError raised.
        """
        activator = HookActivator(project_root="/tmp/test")
        invalid = {"hooks": "not a dict"}

        with pytest.raises(SettingsValidationError, match="'hooks' must be a dictionary"):
            activator._validate_settings(invalid)

    def test_validate_settings_lifecycle_value_not_list(self, mock_security_utils):
        """Test validation fails when lifecycle event value is not a list.

        REQUIREMENT: Each lifecycle event must map to a list of hooks.
        Expected: SettingsValidationError raised.
        """
        activator = HookActivator(project_root="/tmp/test")
        invalid = {
            "hooks": {
                "UserPromptSubmit": "not a list"
            }
        }

        with pytest.raises(SettingsValidationError, match="must be a list"):
            activator._validate_settings(invalid)

    def test_validate_settings_hook_not_string(self, mock_security_utils):
        """Test validation fails when hook filename is not a string.

        REQUIREMENT: Hook filenames must be strings.
        Expected: SettingsValidationError raised.
        """
        activator = HookActivator(project_root="/tmp/test")
        invalid = {
            "hooks": {
                "UserPromptSubmit": [123, "valid_hook.py"]
            }
        }

        with pytest.raises(SettingsValidationError, match="must be strings"):
            activator._validate_settings(invalid)


# ============================================================================
# Test Atomic Write Operations
# ============================================================================


class TestAtomicWrite:
    """Test atomic write with tempfile + rename pattern."""

    def test_atomic_write_creates_temp_file(self, temp_claude_dir, temp_project_root, new_hooks, mock_security_utils):
        """Test atomic write creates temporary file before rename.

        REQUIREMENT: Use tempfile for atomic write (prevent corruption).
        Expected: Temp file created with mkstemp, then renamed.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_fd = 10
            mock_temp_path = str(temp_claude_dir / "settings.json.tmp.12345")
            mock_mkstemp.return_value = (mock_fd, mock_temp_path)

            with patch("os.write") as mock_write:
                with patch("os.close") as mock_close:
                    with patch("os.rename") as mock_rename:
                        activator._atomic_write_settings(new_hooks)

                        # Verify mkstemp called
                        mock_mkstemp.assert_called_once()
                        # Verify write called with fd
                        mock_write.assert_called()
                        # Verify close called
                        mock_close.assert_called_once_with(mock_fd)
                        # Verify rename called
                        mock_rename.assert_called_once()

    def test_atomic_write_sets_permissions(self, temp_claude_dir, temp_project_root, new_hooks, mock_security_utils):
        """Test atomic write sets secure permissions on settings file.

        REQUIREMENT: Settings file should have user-only permissions (0o600).
        Expected: chmod called with 0o600.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_fd = 10
            mock_temp_path = str(temp_claude_dir / "settings.json.tmp")
            mock_mkstemp.return_value = (mock_fd, mock_temp_path)

            with patch("os.write"):
                with patch("os.close"):
                    with patch("os.chmod") as mock_chmod:
                        with patch("os.rename"):
                            activator._atomic_write_settings(new_hooks)

                            # Verify chmod called with 0o600
                            mock_chmod.assert_called_with(mock_temp_path, 0o600)

    def test_atomic_write_cleanup_on_error(self, temp_claude_dir, temp_project_root, new_hooks, mock_security_utils):
        """Test atomic write cleans up temp file on error.

        REQUIREMENT: Clean up temp file if write fails.
        Expected: Temp file removed even if rename fails.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_fd = 10
            mock_temp_path = str(temp_claude_dir / "settings.json.tmp")
            mock_mkstemp.return_value = (mock_fd, mock_temp_path)

            with patch("os.write"):
                with patch("os.close"):
                    with patch("os.rename") as mock_rename:
                        # Simulate rename error
                        mock_rename.side_effect = OSError("Disk full")

                        with patch("os.unlink") as mock_unlink:
                            with pytest.raises(ActivationError):
                                activator._atomic_write_settings(new_hooks)

                            # Verify temp file cleaned up
                            mock_unlink.assert_called_with(mock_temp_path)

    def test_atomic_write_disk_full_error(self, temp_project_root, new_hooks, mock_security_utils):
        """Test atomic write handles disk full error.

        REQUIREMENT: Handle disk full gracefully.
        Expected: ActivationError raised with clear message.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.side_effect = OSError("No space left on device")

            with pytest.raises(ActivationError, match="No space left"):
                activator._atomic_write_settings(new_hooks)


# ============================================================================
# Test Main Activation Workflow
# ============================================================================


class TestActivateHooksWorkflow:
    """Test main activate_hooks() workflow integration."""

    def test_activate_hooks_first_install_success(self, temp_project_root, new_hooks, mock_security_utils):
        """Test successful hook activation on first install.

        REQUIREMENT: Activate hooks automatically on first install.
        Expected: ActivationResult with activated=True, first_install=True.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings") as mock_write:
            result = activator.activate_hooks(new_hooks)

            assert result.activated is True
            assert result.first_install is True
            assert result.hooks_added > 0
            assert "Successfully activated" in result.message
            mock_write.assert_called_once()

    def test_activate_hooks_update_scenario_success(self, temp_claude_dir, temp_project_root, sample_settings, new_hooks, mock_security_utils):
        """Test successful hook activation on update.

        REQUIREMENT: Merge hooks on update without losing customizations.
        Expected: ActivationResult with activated=True, first_install=False.
        """
        # Create existing settings
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps(sample_settings))

        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings") as mock_write:
            result = activator.activate_hooks(new_hooks)

            assert result.activated is True
            assert result.first_install is False
            assert "custom_setting" in result.details.get("preserved_settings", [])
            mock_write.assert_called_once()

    def test_activate_hooks_creates_claude_dir_if_missing(self, temp_project_root, new_hooks, mock_security_utils):
        """Test activation creates .claude directory if missing.

        REQUIREMENT: Create .claude directory during first install.
        Expected: .claude directory created before writing settings.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings"):
            result = activator.activate_hooks(new_hooks)

            assert activator.claude_dir.exists()
            assert result.activated is True

    def test_activate_hooks_validation_error_rollback(self, temp_project_root, mock_security_utils):
        """Test activation handles validation errors gracefully.

        REQUIREMENT: Don't write invalid settings.
        Expected: ActivationError raised, no file written.
        """
        activator = HookActivator(project_root=temp_project_root)

        # Invalid hooks (missing 'hooks' key)
        invalid_hooks = {"custom": "value"}

        with patch.object(activator, "_atomic_write_settings") as mock_write:
            with pytest.raises(SettingsValidationError):
                activator.activate_hooks(invalid_hooks)

            # Verify write was NOT called
            mock_write.assert_not_called()

    def test_activate_hooks_audit_logging(self, temp_project_root, new_hooks, mock_security_utils):
        """Test activation logs to security audit.

        REQUIREMENT: Audit log all hook activation operations (CWE-778).
        Expected: audit_log called with activation details.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings"):
            result = activator.activate_hooks(new_hooks)

            # Verify audit logging
            mock_security_utils.audit_log.assert_called()
            # Check log contains operation details
            call_args = mock_security_utils.audit_log.call_args
            assert "hook_activation" in str(call_args).lower()

    def test_activate_hooks_no_hooks_provided(self, temp_project_root, mock_security_utils):
        """Test activation handles empty hooks gracefully.

        REQUIREMENT: Handle edge case of no hooks to activate.
        Expected: ActivationResult with activated=False.
        """
        activator = HookActivator(project_root=temp_project_root)
        empty_hooks = {"hooks": {}}

        result = activator.activate_hooks(empty_hooks)

        assert result.activated is False
        assert result.hooks_added == 0
        assert "No hooks to activate" in result.message


# ============================================================================
# Test Edge Cases and Error Handling
# ============================================================================


class TestEdgeCasesAndErrors:
    """Test edge cases and error handling."""

    def test_readonly_filesystem_error(self, temp_project_root, new_hooks, mock_security_utils):
        """Test activation handles read-only filesystem.

        REQUIREMENT: Handle permission errors gracefully.
        Expected: ActivationError with clear message.
        """
        activator = HookActivator(project_root=temp_project_root)

        with patch("tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.side_effect = PermissionError("Read-only file system")

            with pytest.raises(ActivationError, match="Read-only"):
                activator.activate_hooks(new_hooks)

    def test_custom_hooks_preserved_during_merge(self, temp_claude_dir, temp_project_root, mock_security_utils):
        """Test merging preserves user's custom hooks.

        REQUIREMENT: Don't remove hooks user manually added.
        Expected: Custom hooks retained after merge.
        """
        # Existing settings with custom hook
        existing = {
            "hooks": {
                "UserPromptSubmit": [
                    "display_project_context.py",
                    "my_custom_hook.py"  # User's custom hook
                ]
            }
        }
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps(existing))

        # New hooks
        new = {
            "hooks": {
                "UserPromptSubmit": [
                    "display_project_context.py",
                    "enforce_command_limit.py"
                ]
            }
        }

        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings") as mock_write:
            result = activator.activate_hooks(new)

            # Get merged settings from write call
            merged = mock_write.call_args[0][0]
            user_prompt_hooks = merged["hooks"]["UserPromptSubmit"]

            # Verify custom hook preserved
            assert "my_custom_hook.py" in user_prompt_hooks
            # Verify new hook added
            assert "enforce_command_limit.py" in user_prompt_hooks

    def test_unicode_in_settings_json(self, temp_claude_dir, temp_project_root, new_hooks, mock_security_utils):
        """Test activation handles unicode characters in settings.

        REQUIREMENT: Support international characters in settings.
        Expected: Unicode preserved correctly.
        """
        # Existing settings with unicode
        existing = {
            "hooks": {},
            "description": "Plugin für Entwicklung 开发插件"
        }
        settings_path = temp_claude_dir / "settings.json"
        settings_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

        activator = HookActivator(project_root=temp_project_root)

        with patch.object(activator, "_atomic_write_settings") as mock_write:
            result = activator.activate_hooks(new_hooks)

            # Verify unicode preserved
            merged = mock_write.call_args[0][0]
            assert "für" in merged["description"]
            assert "开发" in merged["description"]

    def test_symlink_attack_prevention(self, temp_project_root, mock_security_utils):
        """Test activation prevents symlink attacks.

        REQUIREMENT: Security - prevent symlink attacks (CWE-59).
        Expected: Validation rejects symlink paths.
        """
        # Mock validation to detect symlink
        mock_security_utils.validate_path.side_effect = ValueError(
            "Symlink detected in path"
        )

        with pytest.raises(ValueError, match="Symlink detected"):
            HookActivator(project_root="/tmp/symlink_attack")
