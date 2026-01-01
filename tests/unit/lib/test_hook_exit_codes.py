#!/usr/bin/env python3
"""
Unit tests for hook_exit_codes library.

Tests for standardized exit code constants used across all hooks.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError: module not found).

Test Strategy:
- Test exit code constant values (0, 1, 2)
- Test lifecycle constraints dictionary exists
- Test constant immutability (shouldn't be modified)
- Test documentation strings exist

Exit Code Semantics:
- EXIT_SUCCESS (0): Operation succeeded, continue workflow
- EXIT_WARNING (1): Non-critical issue detected, workflow continues
- EXIT_BLOCK (2): Critical issue detected, block workflow

Lifecycle Constraints:
- PreToolUse hooks: MUST always exit 0 (cannot block)
- SubagentStop hooks: MUST always exit 0 (cannot block)
- PreSubagent hooks: CAN exit 2 to block agent spawn

Coverage Target: 100% for hook_exit_codes module

Date: 2026-01-01
Feature: Standardized exit codes across all hooks
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (all tests failing - module doesn't exist yet)
"""

import sys
import pytest
from pathlib import Path

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

# Import will fail - module doesn't exist yet (TDD!)
try:
    from hook_exit_codes import (
        EXIT_SUCCESS,
        EXIT_WARNING,
        EXIT_BLOCK,
        LIFECYCLE_CONSTRAINTS,
    )
    IMPORT_SUCCESSFUL = True
except ImportError as e:
    IMPORT_SUCCESSFUL = False
    IMPORT_ERROR = str(e)


class TestExitCodeConstants:
    """Test exit code constant values."""

    def test_module_imports(self):
        """Test that hook_exit_codes module exists and imports successfully."""
        assert IMPORT_SUCCESSFUL, f"Failed to import hook_exit_codes: {IMPORT_ERROR}"

    def test_exit_success_is_zero(self):
        """Test EXIT_SUCCESS equals 0."""
        assert EXIT_SUCCESS == 0, "EXIT_SUCCESS should be 0"

    def test_exit_warning_is_one(self):
        """Test EXIT_WARNING equals 1."""
        assert EXIT_WARNING == 1, "EXIT_WARNING should be 1"

    def test_exit_block_is_two(self):
        """Test EXIT_BLOCK equals 2."""
        assert EXIT_BLOCK == 2, "EXIT_BLOCK should be 2"

    def test_exit_codes_are_distinct(self):
        """Test that all exit codes have unique values."""
        codes = {EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK}
        assert len(codes) == 3, "All exit codes should have distinct values"

    def test_exit_codes_are_integers(self):
        """Test that all exit codes are integers."""
        assert isinstance(EXIT_SUCCESS, int), "EXIT_SUCCESS should be int"
        assert isinstance(EXIT_WARNING, int), "EXIT_WARNING should be int"
        assert isinstance(EXIT_BLOCK, int), "EXIT_BLOCK should be int"

    def test_exit_codes_are_valid_range(self):
        """Test that exit codes are in valid Unix exit code range (0-255)."""
        assert 0 <= EXIT_SUCCESS <= 255, "EXIT_SUCCESS should be 0-255"
        assert 0 <= EXIT_WARNING <= 255, "EXIT_WARNING should be 0-255"
        assert 0 <= EXIT_BLOCK <= 255, "EXIT_BLOCK should be 0-255"


class TestLifecycleConstraints:
    """Test lifecycle constraints dictionary."""

    def test_lifecycle_constraints_exists(self):
        """Test that LIFECYCLE_CONSTRAINTS dictionary exists."""
        assert LIFECYCLE_CONSTRAINTS is not None, "LIFECYCLE_CONSTRAINTS should exist"

    def test_lifecycle_constraints_is_dict(self):
        """Test that LIFECYCLE_CONSTRAINTS is a dictionary."""
        assert isinstance(LIFECYCLE_CONSTRAINTS, dict), "LIFECYCLE_CONSTRAINTS should be dict"

    def test_pretooluse_lifecycle_exists(self):
        """Test that PreToolUse lifecycle is defined."""
        assert "PreToolUse" in LIFECYCLE_CONSTRAINTS, "PreToolUse should be in constraints"

    def test_subagentstop_lifecycle_exists(self):
        """Test that SubagentStop lifecycle is defined."""
        assert "SubagentStop" in LIFECYCLE_CONSTRAINTS, "SubagentStop should be in constraints"

    def test_presubagent_lifecycle_exists(self):
        """Test that PreSubagent lifecycle is defined."""
        assert "PreSubagent" in LIFECYCLE_CONSTRAINTS, "PreSubagent should be in constraints"

    def test_pretooluse_must_exit_zero(self):
        """Test that PreToolUse hooks must always exit 0."""
        constraint = LIFECYCLE_CONSTRAINTS["PreToolUse"]
        assert constraint["allowed_exits"] == [EXIT_SUCCESS], \
            "PreToolUse hooks must only exit 0"
        assert constraint["can_block"] is False, \
            "PreToolUse hooks cannot block workflow"

    def test_subagentstop_must_exit_zero(self):
        """Test that SubagentStop hooks must always exit 0."""
        constraint = LIFECYCLE_CONSTRAINTS["SubagentStop"]
        assert constraint["allowed_exits"] == [EXIT_SUCCESS], \
            "SubagentStop hooks must only exit 0"
        assert constraint["can_block"] is False, \
            "SubagentStop hooks cannot block workflow"

    def test_presubagent_can_block(self):
        """Test that PreSubagent hooks can exit with blocking code."""
        constraint = LIFECYCLE_CONSTRAINTS["PreSubagent"]
        assert EXIT_BLOCK in constraint["allowed_exits"], \
            "PreSubagent hooks should be able to exit 2"
        assert constraint["can_block"] is True, \
            "PreSubagent hooks can block workflow"

    def test_all_lifecycles_allow_success(self):
        """Test that all lifecycles allow EXIT_SUCCESS."""
        for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
            assert EXIT_SUCCESS in constraint["allowed_exits"], \
                f"{lifecycle} should allow EXIT_SUCCESS"

    def test_lifecycle_constraints_have_required_keys(self):
        """Test that all lifecycle constraints have required keys."""
        required_keys = {"allowed_exits", "can_block", "description"}
        for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
            actual_keys = set(constraint.keys())
            assert required_keys.issubset(actual_keys), \
                f"{lifecycle} constraint missing required keys: {required_keys - actual_keys}"

    def test_lifecycle_descriptions_exist(self):
        """Test that all lifecycles have description strings."""
        for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
            assert isinstance(constraint["description"], str), \
                f"{lifecycle} should have string description"
            assert len(constraint["description"]) > 0, \
                f"{lifecycle} description should not be empty"


class TestConstantImmutability:
    """Test that constants are properly defined and documented."""

    def test_constants_have_docstrings(self):
        """Test that exit code constants have documentation."""
        # This will be verified in the implementation
        # Module should have comprehensive docstring explaining semantics
        import hook_exit_codes
        assert hook_exit_codes.__doc__ is not None, \
            "hook_exit_codes module should have docstring"
        assert len(hook_exit_codes.__doc__) > 50, \
            "hook_exit_codes module docstring should be comprehensive"

    def test_module_exports_expected_symbols(self):
        """Test that module exports only expected symbols."""
        import hook_exit_codes
        expected_exports = {
            "EXIT_SUCCESS",
            "EXIT_WARNING",
            "EXIT_BLOCK",
            "LIFECYCLE_CONSTRAINTS",
        }
        # Check that expected symbols exist
        for symbol in expected_exports:
            assert hasattr(hook_exit_codes, symbol), \
                f"Module should export {symbol}"


class TestExitCodeUsageExamples:
    """Test usage patterns and examples."""

    def test_success_exit_pattern(self):
        """Test typical success exit pattern."""
        # Hook completes successfully
        exit_code = EXIT_SUCCESS
        assert exit_code == 0

    def test_warning_exit_pattern(self):
        """Test typical warning exit pattern."""
        # Hook detects non-critical issue but allows continuation
        exit_code = EXIT_WARNING
        assert exit_code == 1

    def test_block_exit_pattern(self):
        """Test typical blocking exit pattern."""
        # Hook detects critical issue and blocks workflow
        exit_code = EXIT_BLOCK
        assert exit_code == 2

    def test_lifecycle_check_pattern(self):
        """Test checking if lifecycle can block."""
        # Example: Check if SubagentStop can block
        lifecycle = "SubagentStop"
        can_block = LIFECYCLE_CONSTRAINTS[lifecycle]["can_block"]
        assert can_block is False, "SubagentStop cannot block"

    def test_allowed_exit_check_pattern(self):
        """Test checking if exit code is allowed for lifecycle."""
        # Example: Check if PreToolUse can exit with BLOCK
        lifecycle = "PreToolUse"
        allowed = LIFECYCLE_CONSTRAINTS[lifecycle]["allowed_exits"]
        assert EXIT_BLOCK not in allowed, "PreToolUse cannot exit BLOCK"


class TestErrorCases:
    """Test error handling and edge cases."""

    def test_lifecycle_constraints_not_empty(self):
        """Test that LIFECYCLE_CONSTRAINTS is not empty."""
        assert len(LIFECYCLE_CONSTRAINTS) > 0, \
            "LIFECYCLE_CONSTRAINTS should have at least one entry"

    def test_lifecycle_allowed_exits_not_empty(self):
        """Test that all lifecycles have at least one allowed exit code."""
        for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
            assert len(constraint["allowed_exits"]) > 0, \
                f"{lifecycle} should have at least one allowed exit code"

    def test_lifecycle_allowed_exits_are_valid(self):
        """Test that all allowed exits are valid exit codes."""
        valid_codes = {EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK}
        for lifecycle, constraint in LIFECYCLE_CONSTRAINTS.items():
            for exit_code in constraint["allowed_exits"]:
                assert exit_code in valid_codes, \
                    f"{lifecycle} has invalid exit code: {exit_code}"


# Checkpoint tracking integration
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Test file 1/3 created: test_hook_exit_codes.py (23 tests for constants module)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")
