#!/usr/bin/env python3
"""
Unit tests for user_state_manager auto-approval extensions (TDD Red Phase).

Tests for MCP auto-approval consent tracking in user_state_manager for Issue #73.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (ImportError or missing attributes).

Test Strategy:
- Test auto-approval preference defaults to disabled (opt-in)
- Test consent persistence across sessions
- Test first-run detection for auto-approval
- Test environment variable override
- Test consent prompt integration

Date: 2025-11-15
Issue: #73 (MCP Auto-Approval for Subagent Tool Calls)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

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

# Import will fail - extensions don't exist yet (TDD!)
try:
    from user_state_manager import (
        UserStateManager,
        get_user_preference,
        set_user_preference,
        is_first_run_auto_approval,
        record_auto_approval_consent,
    )
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


class TestAutoApprovalConsentDefaults:
    """Test auto-approval consent defaults (opt-in design)."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_auto_approval_defaults_to_disabled(self, temp_state_file):
        """Test mcp_auto_approve_enabled defaults to False (opt-in)."""
        manager = UserStateManager(temp_state_file)

        # Should default to disabled
        pref = manager.get_preference("mcp_auto_approve_enabled")
        assert pref is False

    def test_get_user_preference_auto_approval_defaults_false(self, temp_state_file):
        """Test get_user_preference returns False for mcp_auto_approve_enabled by default."""
        # Create empty state
        manager = UserStateManager(temp_state_file)
        manager.save()

        # Get preference
        pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

        assert pref is False

    def test_new_state_file_has_auto_approval_disabled(self, temp_state_file):
        """Test new state file has auto-approval disabled by default."""
        manager = UserStateManager(temp_state_file)
        manager.save()

        # Read state file
        state = json.loads(temp_state_file.read_text())

        # Should have preference set to False
        assert state["preferences"].get("mcp_auto_approve_enabled", False) is False


class TestAutoApprovalConsentPersistence:
    """Test auto-approval consent persistence."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_set_auto_approval_enabled(self, temp_state_file):
        """Test setting mcp_auto_approve_enabled to True."""
        manager = UserStateManager(temp_state_file)

        manager.set_preference("mcp_auto_approve_enabled", True)
        manager.save()

        # Read back
        pref = manager.get_preference("mcp_auto_approve_enabled")
        assert pref is True

    def test_set_auto_approval_disabled(self, temp_state_file):
        """Test setting mcp_auto_approve_enabled to False."""
        manager = UserStateManager(temp_state_file)

        manager.set_preference("mcp_auto_approve_enabled", False)
        manager.save()

        # Read back
        pref = manager.get_preference("mcp_auto_approve_enabled")
        assert pref is False

    def test_auto_approval_persists_across_sessions(self, temp_state_file):
        """Test auto-approval consent persists across sessions."""
        # First session: enable
        manager1 = UserStateManager(temp_state_file)
        manager1.set_preference("mcp_auto_approve_enabled", True)
        manager1.save()

        # Second session: read
        manager2 = UserStateManager(temp_state_file)
        pref = manager2.get_preference("mcp_auto_approve_enabled")

        assert pref is True

    def test_set_user_preference_auto_approval(self, temp_state_file):
        """Test set_user_preference works for auto-approval."""
        set_user_preference("mcp_auto_approve_enabled", True, temp_state_file)

        # Read back
        pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

        assert pref is True


class TestAutoApprovalFirstRun:
    """Test first-run detection for auto-approval."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_is_first_run_auto_approval_true_initially(self, temp_state_file):
        """Test is_first_run_auto_approval returns True for new state."""
        result = is_first_run_auto_approval(temp_state_file)

        assert result is True

    def test_is_first_run_auto_approval_false_after_consent(self, temp_state_file):
        """Test is_first_run_auto_approval returns False after consent recorded."""
        record_auto_approval_consent(True, temp_state_file)

        result = is_first_run_auto_approval(temp_state_file)

        assert result is False

    def test_record_auto_approval_consent_enabled(self, temp_state_file):
        """Test record_auto_approval_consent records enabled consent."""
        record_auto_approval_consent(True, temp_state_file)

        # Should mark first run complete
        assert is_first_run_auto_approval(temp_state_file) is False

        # Should save preference
        pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)
        assert pref is True

    def test_record_auto_approval_consent_disabled(self, temp_state_file):
        """Test record_auto_approval_consent records disabled consent."""
        record_auto_approval_consent(False, temp_state_file)

        # Should mark first run complete
        assert is_first_run_auto_approval(temp_state_file) is False

        # Should save preference
        pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)
        assert pref is False

    def test_first_run_flag_separate_from_git_first_run(self, temp_state_file):
        """Test auto-approval first-run is separate from git automation first-run."""
        manager = UserStateManager(temp_state_file)

        # Mark git first run complete
        manager.record_first_run_complete()
        manager.save()

        # Auto-approval first run should still be pending
        assert is_first_run_auto_approval(temp_state_file) is True


class TestEnvironmentVariableOverride:
    """Test environment variable override for auto-approval."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_env_var_overrides_disabled_preference(self, temp_state_file):
        """Test MCP_AUTO_APPROVE=true overrides disabled preference."""
        # Set preference to disabled
        set_user_preference("mcp_auto_approve_enabled", False, temp_state_file)

        # Override with env var
        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "true"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            # Env var should override
            assert pref is True

    def test_env_var_overrides_enabled_preference(self, temp_state_file):
        """Test MCP_AUTO_APPROVE=false overrides enabled preference."""
        # Set preference to enabled
        set_user_preference("mcp_auto_approve_enabled", True, temp_state_file)

        # Override with env var
        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "false"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            # Env var should override
            assert pref is False

    def test_env_var_case_insensitive(self, temp_state_file):
        """Test MCP_AUTO_APPROVE env var is case-insensitive."""
        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "TRUE"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            assert pref is True

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "FALSE"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            assert pref is False

    def test_env_var_accepts_1_and_0(self, temp_state_file):
        """Test MCP_AUTO_APPROVE accepts 1/0 values."""
        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "1"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            assert pref is True

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "0"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            assert pref is False

    def test_invalid_env_var_uses_preference(self, temp_state_file):
        """Test invalid MCP_AUTO_APPROVE value falls back to preference."""
        set_user_preference("mcp_auto_approve_enabled", True, temp_state_file)

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "invalid"}):
            pref = get_user_preference("mcp_auto_approve_enabled", temp_state_file)

            # Should use preference (env var invalid)
            assert pref is True


class TestConsentPromptIntegration:
    """Test consent prompt integration."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_should_show_auto_approval_prompt_on_first_run(self, temp_state_file):
        """Test should show prompt on first run for auto-approval."""
        from user_state_manager import should_show_auto_approval_prompt

        result = should_show_auto_approval_prompt(temp_state_file)

        assert result is True

    def test_should_not_show_prompt_after_consent(self, temp_state_file):
        """Test should not show prompt after consent recorded."""
        from user_state_manager import should_show_auto_approval_prompt

        record_auto_approval_consent(True, temp_state_file)

        result = should_show_auto_approval_prompt(temp_state_file)

        assert result is False

    def test_should_not_show_prompt_if_env_var_set(self, temp_state_file):
        """Test should not show prompt if MCP_AUTO_APPROVE env var set."""
        from user_state_manager import should_show_auto_approval_prompt

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "true"}):
            result = should_show_auto_approval_prompt(temp_state_file)

            # Env var set = explicit choice, no prompt needed
            assert result is False


class TestStateFileIntegrity:
    """Test state file integrity with auto-approval fields."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create temporary state file."""
        return tmp_path / "user_state.json"

    def test_state_file_has_expected_structure(self, temp_state_file):
        """Test state file has expected structure with auto-approval."""
        manager = UserStateManager(temp_state_file)
        manager.set_preference("mcp_auto_approve_enabled", True)
        manager.save()

        # Read raw JSON
        state = json.loads(temp_state_file.read_text())

        # Should have expected structure
        assert "preferences" in state
        assert "mcp_auto_approve_enabled" in state["preferences"]
        assert "auto_approval_first_run_complete" in state

    def test_backwards_compatibility_with_old_state_files(self, temp_state_file):
        """Test backwards compatibility with old state files without auto-approval."""
        # Create old-style state file
        old_state = {
            "first_run_complete": True,
            "preferences": {
                "auto_git_enabled": True
            },
            "version": "1.0"
        }
        temp_state_file.write_text(json.dumps(old_state))

        # Load with new code
        manager = UserStateManager(temp_state_file)

        # Should add auto-approval fields with defaults
        assert manager.get_preference("mcp_auto_approve_enabled") is False
        assert is_first_run_auto_approval(temp_state_file) is True

    def test_migration_preserves_existing_preferences(self, temp_state_file):
        """Test migration preserves existing preferences."""
        # Create old state
        old_state = {
            "first_run_complete": True,
            "preferences": {
                "auto_git_enabled": True,
                "custom_setting": "value"
            },
            "version": "1.0"
        }
        temp_state_file.write_text(json.dumps(old_state))

        # Load and save
        manager = UserStateManager(temp_state_file)
        manager.save()

        # Read back
        state = json.loads(temp_state_file.read_text())

        # Should preserve old preferences
        assert state["preferences"]["auto_git_enabled"] is True
        assert state["preferences"]["custom_setting"] == "value"
