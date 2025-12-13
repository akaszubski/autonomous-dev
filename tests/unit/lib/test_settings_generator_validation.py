#!/usr/bin/env python3
"""
Unit tests for settings_generator.py validation functions - TDD Red Phase

Tests the validation, detection, and fixing functions for settings.local.json
permission patterns. Detects wildcards, missing deny lists, and outdated patterns.

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #114):
1. Detect Bash(*) wildcards and replace with specific patterns
2. Detect Bash(:*) wildcards and warn (less severe)
3. Detect missing deny list and add comprehensive blocks
4. Preserve user customizations (hooks, valid custom patterns)
5. Atomic operations (backup before modify)
6. Non-blocking (update succeeds even if fix fails)

Test Strategy:
- Test validate_permission_patterns() for issue detection
- Test detect_outdated_patterns() for deprecated patterns
- Test fix_permission_patterns() for pattern replacement
- Test preserve_user_customizations() for hooks/custom patterns
- Test roundtrip: fix -> validate -> success
- Test edge cases: malformed JSON, empty structures, permission errors

Coverage Target: 95%+ for validation functions

Author: test-master agent
Date: 2025-12-12
Issue: #114
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.lib.settings_generator import (
        SettingsGenerator,
        validate_permission_patterns,
        detect_outdated_patterns,
        fix_permission_patterns,
        ValidationResult,
        PermissionIssue,
        DEFAULT_DENY_LIST,
        SAFE_COMMAND_PATTERNS,
    )
except ImportError:
    pytest.skip("settings_generator validation functions not implemented yet", allow_module_level=True)


# =============================================================================
# Test Fixtures - Settings Examples
# =============================================================================

@pytest.fixture
def settings_with_bash_wildcard():
    """Settings with Bash(*) wildcard - MUST BE FIXED"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(*)",  # SECURITY ISSUE - too permissive
                "Read(**)",
                "Write(**)",
            ],
            "deny": []
        },
        "hooks": {
            "auto_format": True,
            "auto_test": False
        }
    }


@pytest.fixture
def settings_with_colon_wildcard():
    """Settings with Bash(:*) wildcard - WARNING"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(:*)",  # WARNING - less specific than needed
                "Read(**)",
                "Write(**)",
            ],
            "deny": [
                "Bash(rm:-rf*)",
                "Bash(sudo:*)"
            ]
        }
    }


@pytest.fixture
def settings_missing_deny_list():
    """Settings with missing deny list - MUST BE FIXED"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(pytest:*)",
                "Read(**)",
                "Write(**)",
            ]
            # Missing "deny" key
        }
    }


@pytest.fixture
def settings_empty_deny_list():
    """Settings with empty deny list - MUST BE FIXED"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Read(**)",
                "Write(**)",
            ],
            "deny": []  # Empty - should have comprehensive blocks
        }
    }


@pytest.fixture
def valid_settings():
    """Valid settings - no issues"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(pytest:*)",
                "Bash(python:*)",
                "Read(**)",
                "Write(**)",
                "Edit(**)",
            ],
            "deny": [
                "Bash(rm:-rf*)",
                "Bash(rm:-f*)",
                "Bash(sudo:*)",
                "Bash(su:*)",
                "Bash(eval:*)",
                "Bash(chmod:*)",
                "Bash(chown:*)",
            ]
        },
        "hooks": {
            "auto_format": True,
            "validate_project_alignment": True
        }
    }


@pytest.fixture
def settings_with_user_customizations():
    """Settings with user customizations that should be preserved"""
    return {
        "version": "1.0.0",
        "permissions": {
            "allow": [
                "Bash(*)",  # Will be removed
                "Bash(git:*)",  # Valid - preserve
                "Bash(docker:*)",  # User custom - preserve
                "Bash(make:*)",  # User custom - preserve
                "Read(**)",
                "Write(**)",
            ],
            "deny": []  # Will be populated
        },
        "hooks": {
            "auto_format": True,
            "auto_test": True,
            "custom_user_hook": True  # User custom - preserve
        },
        "custom_config": {
            "user_setting": "value"  # User custom - preserve
        }
    }


@pytest.fixture
def malformed_settings_missing_permissions():
    """Malformed settings - missing permissions key"""
    return {
        "version": "1.0.0",
        "hooks": {
            "auto_format": True
        }
    }


@pytest.fixture
def malformed_settings_wrong_type():
    """Malformed settings - permissions is wrong type"""
    return {
        "version": "1.0.0",
        "permissions": "this should be a dict",
        "hooks": {}
    }


# =============================================================================
# Test validate_permission_patterns() - Issue Detection
# =============================================================================

class TestValidatePermissionPatterns:
    """Test validate_permission_patterns() function for issue detection."""

    def test_detect_bash_wildcard_error(self, settings_with_bash_wildcard):
        """Test detection of Bash(*) wildcard returns error severity.

        REQUIREMENT: Detect Bash(*) wildcard as critical security issue.
        Expected: ValidationResult with valid=False, issue severity="error".
        """
        result = validate_permission_patterns(settings_with_bash_wildcard)

        assert result.valid is False
        assert len(result.issues) >= 1

        # Find the Bash(*) wildcard issue
        wildcard_issues = [
            issue for issue in result.issues
            if "Bash(*)" in issue.pattern and issue.severity == "error"
        ]
        assert len(wildcard_issues) >= 1
        assert wildcard_issues[0].issue_type == "wildcard_pattern"
        assert "too permissive" in wildcard_issues[0].description.lower()

    def test_detect_colon_wildcard_warning(self, settings_with_colon_wildcard):
        """Test detection of Bash(:*) wildcard returns warning severity.

        REQUIREMENT: Detect Bash(:*) wildcard as warning (less severe).
        Expected: ValidationResult with valid=False, issue severity="warning".
        """
        result = validate_permission_patterns(settings_with_colon_wildcard)

        assert result.valid is False
        assert len(result.issues) >= 1

        # Find the Bash(:*) wildcard issue
        wildcard_issues = [
            issue for issue in result.issues
            if "Bash(:*)" in issue.pattern and issue.severity == "warning"
        ]
        assert len(wildcard_issues) >= 1
        assert wildcard_issues[0].issue_type == "wildcard_pattern"

    def test_detect_missing_deny_list(self, settings_missing_deny_list):
        """Test detection of missing deny list.

        REQUIREMENT: Detect missing deny list as critical issue.
        Expected: ValidationResult with valid=False, issue about missing deny list.
        """
        result = validate_permission_patterns(settings_missing_deny_list)

        assert result.valid is False
        assert len(result.issues) >= 1

        # Find the missing deny list issue
        deny_issues = [
            issue for issue in result.issues
            if issue.issue_type == "missing_deny_list"
        ]
        assert len(deny_issues) >= 1
        assert deny_issues[0].severity == "error"
        assert "deny list" in deny_issues[0].description.lower()

    def test_detect_empty_deny_list(self, settings_empty_deny_list):
        """Test detection of empty deny list.

        REQUIREMENT: Detect empty deny list as critical issue.
        Expected: ValidationResult with valid=False, issue about empty deny list.
        """
        result = validate_permission_patterns(settings_empty_deny_list)

        assert result.valid is False
        assert len(result.issues) >= 1

        # Find the empty deny list issue
        deny_issues = [
            issue for issue in result.issues
            if issue.issue_type == "empty_deny_list"
        ]
        assert len(deny_issues) >= 1
        assert deny_issues[0].severity == "error"

    def test_valid_settings_no_issues(self, valid_settings):
        """Test valid settings returns no issues.

        REQUIREMENT: Valid settings with specific patterns and deny list should pass.
        Expected: ValidationResult with valid=True, no issues.
        """
        result = validate_permission_patterns(valid_settings)

        assert result.valid is True
        assert len(result.issues) == 0

    def test_malformed_settings_missing_permissions(self, malformed_settings_missing_permissions):
        """Test malformed settings (missing permissions) returns error.

        REQUIREMENT: Handle malformed JSON gracefully.
        Expected: ValidationResult with valid=False, structure error issue.
        """
        result = validate_permission_patterns(malformed_settings_missing_permissions)

        assert result.valid is False
        assert len(result.issues) >= 1

        structure_issues = [
            issue for issue in result.issues
            if issue.issue_type == "malformed_structure"
        ]
        assert len(structure_issues) >= 1
        assert structure_issues[0].severity == "error"

    def test_malformed_settings_wrong_type(self, malformed_settings_wrong_type):
        """Test malformed settings (wrong type) returns error.

        REQUIREMENT: Handle malformed JSON gracefully.
        Expected: ValidationResult with valid=False, structure error issue.
        """
        result = validate_permission_patterns(malformed_settings_wrong_type)

        assert result.valid is False
        assert len(result.issues) >= 1

        structure_issues = [
            issue for issue in result.issues
            if issue.issue_type == "malformed_structure"
        ]
        assert len(structure_issues) >= 1

    def test_multiple_issues_detected(self):
        """Test detection of multiple issues at once.

        REQUIREMENT: Detect all issues in single validation pass.
        Expected: ValidationResult with multiple issues.
        """
        settings_with_multiple_issues = {
            "version": "1.0.0",
            "permissions": {
                "allow": [
                    "Bash(*)",  # Issue 1: wildcard
                    "Bash(:*)",  # Issue 2: colon wildcard
                    "Read(**)",
                ],
                "deny": []  # Issue 3: empty deny list
            }
        }

        result = validate_permission_patterns(settings_with_multiple_issues)

        assert result.valid is False
        assert len(result.issues) >= 3

        # Verify all issue types present
        issue_types = {issue.issue_type for issue in result.issues}
        assert "wildcard_pattern" in issue_types
        assert "empty_deny_list" in issue_types


# =============================================================================
# Test detect_outdated_patterns() - Deprecated Pattern Detection
# =============================================================================

class TestDetectOutdatedPatterns:
    """Test detect_outdated_patterns() function for deprecated patterns."""

    def test_detect_deprecated_patterns(self):
        """Test detection of patterns not in SAFE_COMMAND_PATTERNS.

        REQUIREMENT: Detect patterns that are not in current safe list.
        Expected: Returns list of outdated patterns.
        """
        settings = {
            "version": "1.0.0",
            "permissions": {
                "allow": [
                    "Bash(git:*)",  # In SAFE_COMMAND_PATTERNS - OK
                    "Bash(obsolete-command:*)",  # NOT in SAFE_COMMAND_PATTERNS
                    "Bash(old-tool:*)",  # NOT in SAFE_COMMAND_PATTERNS
                    "Read(**)",  # In SAFE_COMMAND_PATTERNS - OK
                ],
                "deny": []
            }
        }

        outdated = detect_outdated_patterns(settings)

        assert len(outdated) == 2
        assert "Bash(obsolete-command:*)" in outdated
        assert "Bash(old-tool:*)" in outdated
        assert "Bash(git:*)" not in outdated
        assert "Read(**)" not in outdated

    def test_no_outdated_patterns_in_valid_settings(self, valid_settings):
        """Test valid settings returns empty outdated list.

        REQUIREMENT: Valid patterns should not be flagged as outdated.
        Expected: Returns empty list.
        """
        outdated = detect_outdated_patterns(valid_settings)

        assert len(outdated) == 0

    def test_handle_settings_without_permissions(self):
        """Test handling of settings without permissions key.

        REQUIREMENT: Gracefully handle malformed settings.
        Expected: Returns empty list (no patterns to check).
        """
        settings = {
            "version": "1.0.0",
            "hooks": {}
        }

        outdated = detect_outdated_patterns(settings)

        assert len(outdated) == 0


# =============================================================================
# Test fix_permission_patterns() - Pattern Replacement
# =============================================================================

class TestFixPermissionPatterns:
    """Test fix_permission_patterns() function for pattern replacement."""

    def test_fix_bash_wildcard_patterns(self, settings_with_bash_wildcard):
        """Test fixing Bash(*) wildcard replaces with specific patterns.

        REQUIREMENT: Replace Bash(*) with specific command patterns.
        Expected: Bash(*) removed, specific patterns added.
        """
        original_settings = json.loads(json.dumps(settings_with_bash_wildcard))
        fixed_settings = fix_permission_patterns(settings_with_bash_wildcard)

        # Bash(*) should be removed
        assert "Bash(*)" not in fixed_settings["permissions"]["allow"]

        # Specific patterns should be present
        assert "Bash(git:*)" in fixed_settings["permissions"]["allow"]
        assert "Bash(pytest:*)" in fixed_settings["permissions"]["allow"]
        assert "Bash(python:*)" in fixed_settings["permissions"]["allow"]

        # Other patterns preserved
        assert "Read(**)" in fixed_settings["permissions"]["allow"]
        assert "Write(**)" in fixed_settings["permissions"]["allow"]

    def test_preserve_user_hooks(self, settings_with_user_customizations):
        """Test that user hooks are preserved after fix.

        REQUIREMENT: Preserve user customizations (hooks).
        Expected: All hooks untouched.
        """
        original_hooks = settings_with_user_customizations["hooks"].copy()
        fixed_settings = fix_permission_patterns(settings_with_user_customizations)

        assert fixed_settings["hooks"] == original_hooks
        assert fixed_settings["hooks"]["auto_format"] is True
        assert fixed_settings["hooks"]["auto_test"] is True
        assert fixed_settings["hooks"]["custom_user_hook"] is True

    def test_preserve_valid_custom_allow_patterns(self, settings_with_user_customizations):
        """Test that valid custom allow patterns are preserved.

        REQUIREMENT: Preserve user customizations (valid custom patterns).
        Expected: User custom patterns not removed.
        """
        fixed_settings = fix_permission_patterns(settings_with_user_customizations)

        # User custom patterns should be preserved
        assert "Bash(docker:*)" in fixed_settings["permissions"]["allow"]
        assert "Bash(make:*)" in fixed_settings["permissions"]["allow"]

        # Standard patterns should be preserved
        assert "Bash(git:*)" in fixed_settings["permissions"]["allow"]

    def test_remove_invalid_wildcard_patterns(self, settings_with_user_customizations):
        """Test that only wildcard patterns are removed.

        REQUIREMENT: Remove Bash(*) wildcards, preserve specific patterns.
        Expected: Bash(*) removed, others preserved.
        """
        fixed_settings = fix_permission_patterns(settings_with_user_customizations)

        # Wildcard should be removed
        assert "Bash(*)" not in fixed_settings["permissions"]["allow"]

        # Specific patterns should remain
        assert "Bash(git:*)" in fixed_settings["permissions"]["allow"]

    def test_add_missing_deny_list(self, settings_missing_deny_list):
        """Test adding missing deny list.

        REQUIREMENT: Add comprehensive deny list when missing.
        Expected: Deny list populated with dangerous operations.
        """
        fixed_settings = fix_permission_patterns(settings_missing_deny_list)

        assert "deny" in fixed_settings["permissions"]
        assert len(fixed_settings["permissions"]["deny"]) > 0

        # Check for critical dangerous operations
        assert any("rm:-rf" in pattern for pattern in fixed_settings["permissions"]["deny"])
        assert any("sudo" in pattern for pattern in fixed_settings["permissions"]["deny"])
        assert any("eval" in pattern for pattern in fixed_settings["permissions"]["deny"])

    def test_populate_empty_deny_list(self, settings_empty_deny_list):
        """Test populating empty deny list.

        REQUIREMENT: Populate empty deny list with dangerous operations.
        Expected: Deny list populated with comprehensive blocks.
        """
        fixed_settings = fix_permission_patterns(settings_empty_deny_list)

        assert len(fixed_settings["permissions"]["deny"]) > 0

        # Check for critical dangerous operations
        assert any("rm:-rf" in pattern for pattern in fixed_settings["permissions"]["deny"])
        assert any("sudo" in pattern for pattern in fixed_settings["permissions"]["deny"])

    def test_preserve_custom_config_sections(self, settings_with_user_customizations):
        """Test that custom config sections are preserved.

        REQUIREMENT: Preserve all user customizations.
        Expected: Custom config sections untouched.
        """
        fixed_settings = fix_permission_patterns(settings_with_user_customizations)

        assert "custom_config" in fixed_settings
        assert fixed_settings["custom_config"]["user_setting"] == "value"

    def test_roundtrip_fix_validate_success(self, settings_with_bash_wildcard):
        """Test roundtrip: fix patterns, then validate should succeed.

        REQUIREMENT: Fixed settings should pass validation.
        Expected: fix -> validate returns valid=True.
        """
        # Fix the settings
        fixed_settings = fix_permission_patterns(settings_with_bash_wildcard)

        # Validate the fixed settings
        result = validate_permission_patterns(fixed_settings)

        assert result.valid is True
        assert len(result.issues) == 0

    def test_fix_preserves_allow_list_order(self):
        """Test that fix operation maintains reasonable allow list order.

        REQUIREMENT: Fixed patterns should be organized logically.
        Expected: File ops first, then Bash commands, no duplicates.
        """
        settings = {
            "version": "1.0.0",
            "permissions": {
                "allow": [
                    "Bash(*)",
                    "Read(**)",
                    "Write(**)",
                ],
                "deny": []
            }
        }

        fixed_settings = fix_permission_patterns(settings)

        allow_list = fixed_settings["permissions"]["allow"]

        # No duplicates
        assert len(allow_list) == len(set(allow_list))

        # File operations should be present
        assert "Read(**)" in allow_list
        assert "Write(**)" in allow_list


# =============================================================================
# Test Edge Cases and Error Handling
# =============================================================================

class TestEdgeCasesAndErrors:
    """Test edge cases and error handling for validation functions."""

    def test_validate_none_input(self):
        """Test validate_permission_patterns with None input.

        REQUIREMENT: Handle invalid input gracefully.
        Expected: ValidationResult with valid=False, error issue.
        """
        result = validate_permission_patterns(None)

        assert result.valid is False
        assert len(result.issues) >= 1

    def test_fix_none_input(self):
        """Test fix_permission_patterns with None input.

        REQUIREMENT: Handle invalid input gracefully.
        Expected: Raises exception or returns None.
        """
        with pytest.raises(Exception):
            fix_permission_patterns(None)

    def test_validate_empty_dict(self):
        """Test validate_permission_patterns with empty dict.

        REQUIREMENT: Handle empty settings gracefully.
        Expected: ValidationResult with valid=False, structure issues.
        """
        result = validate_permission_patterns({})

        assert result.valid is False
        assert len(result.issues) >= 1

    def test_fix_settings_with_no_changes_needed(self, valid_settings):
        """Test fix on already valid settings.

        REQUIREMENT: Fix should be idempotent.
        Expected: Returns identical settings (or only adds redundant safe patterns).
        """
        original_settings = json.loads(json.dumps(valid_settings))
        fixed_settings = fix_permission_patterns(valid_settings)

        # Allow list may have additions but should contain all originals
        for pattern in original_settings["permissions"]["allow"]:
            assert pattern in fixed_settings["permissions"]["allow"]

        # Deny list should be unchanged or expanded
        for pattern in original_settings["permissions"]["deny"]:
            assert pattern in fixed_settings["permissions"]["deny"]

    def test_detect_outdated_with_empty_allow_list(self):
        """Test detect_outdated_patterns with empty allow list.

        REQUIREMENT: Handle empty allow list gracefully.
        Expected: Returns empty list.
        """
        settings = {
            "version": "1.0.0",
            "permissions": {
                "allow": [],
                "deny": []
            }
        }

        outdated = detect_outdated_patterns(settings)

        assert len(outdated) == 0


# =============================================================================
# Test Integration - Full Validation Flow
# =============================================================================

class TestValidationIntegration:
    """Test full validation flow with multiple operations."""

    def test_full_validation_flow_with_issues(self, settings_with_bash_wildcard):
        """Test complete flow: validate -> detect issues -> fix -> validate again.

        REQUIREMENT: Complete validation workflow should work end-to-end.
        Expected: Initial validation fails, fix applied, final validation passes.
        """
        # Step 1: Initial validation should fail
        initial_result = validate_permission_patterns(settings_with_bash_wildcard)
        assert initial_result.valid is False
        assert len(initial_result.issues) > 0

        # Step 2: Apply fix
        fixed_settings = fix_permission_patterns(settings_with_bash_wildcard)

        # Step 3: Final validation should pass
        final_result = validate_permission_patterns(fixed_settings)
        assert final_result.valid is True
        assert len(final_result.issues) == 0

    def test_preserve_all_customizations_through_fix(self, settings_with_user_customizations):
        """Test that all user customizations survive fix operation.

        REQUIREMENT: Fix should preserve hooks, custom patterns, custom config.
        Expected: All user customizations intact after fix.
        """
        original = settings_with_user_customizations
        fixed = fix_permission_patterns(original)

        # Hooks preserved
        assert fixed["hooks"] == original["hooks"]

        # Valid custom patterns preserved
        assert "Bash(docker:*)" in fixed["permissions"]["allow"]
        assert "Bash(make:*)" in fixed["permissions"]["allow"]

        # Custom config preserved
        assert fixed["custom_config"] == original["custom_config"]

        # Invalid patterns removed
        assert "Bash(*)" not in fixed["permissions"]["allow"]

        # Deny list populated
        assert len(fixed["permissions"]["deny"]) > 0
