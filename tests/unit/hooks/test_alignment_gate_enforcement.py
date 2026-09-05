"""
Unit tests for Issue #585: Alignment gate enforcement in unified_pre_tool.py.

Validates that:
- Code writes are blocked when alignment_passed is False during explicit /implement
- Code writes are allowed when alignment_passed is True
- Non-code files are not blocked by alignment gate
- Read tools are not affected
- Pipeline agents bypass alignment gate
- Missing/tampered state file fails closed

Date: 2026-03-28
Issue: #585
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hook and lib dirs to path
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Reset relevant env vars for each test."""
    env_keys = [
        "SANDBOX_ENABLED", "PRE_TOOL_MCP_SECURITY", "PRE_TOOL_AGENT_AUTH",
        "PRE_TOOL_BATCH_PERMISSION", "MCP_AUTO_APPROVE", "ENFORCEMENT_LEVEL",
        "CLAUDE_AGENT_NAME", "PIPELINE_STATE_FILE",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "true")
    monkeypatch.setenv("PRE_TOOL_AGENT_AUTH", "true")


@pytest.fixture
def state_file(tmp_path):
    """Create a temporary pipeline state file."""
    state_path = tmp_path / "implement_pipeline_state.json"

    def _write(data: dict) -> str:
        state_path.write_text(json.dumps(data))
        return str(state_path)

    return _write


@pytest.fixture
def aligned_state(state_file, monkeypatch):
    """Create a valid explicit pipeline state WITH alignment_passed=True."""
    from pipeline_state import sign_state
    state = {
        "session_start": datetime.now().isoformat(),
        "mode": "full",
        "run_id": "test-aligned-585",
        "explicitly_invoked": True,
        "alignment_passed": True,
    }
    signed = sign_state(state, "test-session")
    path = state_file(signed)
    monkeypatch.setenv("PIPELINE_STATE_FILE", path)
    return path


@pytest.fixture
def unaligned_state(state_file, monkeypatch):
    """Create a valid explicit pipeline state WITHOUT alignment (alignment_passed=False)."""
    from pipeline_state import sign_state
    state = {
        "session_start": datetime.now().isoformat(),
        "mode": "full",
        "run_id": "test-unaligned-585",
        "explicitly_invoked": True,
        "alignment_passed": False,
    }
    signed = sign_state(state, "test-session")
    path = state_file(signed)
    monkeypatch.setenv("PIPELINE_STATE_FILE", path)
    return path


# ---------------------------------------------------------------------------
# 1. Alignment gate blocks code writes when alignment_passed=False
# ---------------------------------------------------------------------------

class TestAlignmentGateBlocking:
    """Code writes blocked when alignment_passed is False."""

    def test_alignment_not_passed_blocks_code_write(self, unaligned_state, monkeypatch):
        """Write to .py file blocked when alignment_passed=False."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        assert decision == "deny"
        assert "ALIGNMENT GATE" in reason

    def test_alignment_not_passed_blocks_code_edit(self, unaligned_state, monkeypatch):
        """Edit to .py file blocked when alignment_passed=False."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Edit", {"file_path": "/srv/project/app.py", "old_string": "a", "new_string": "b"}
        )
        assert decision == "deny"
        assert "ALIGNMENT GATE" in reason

    def test_alignment_not_passed_blocks_bash_code_write(self, unaligned_state, monkeypatch):
        """Bash command writing to .py file blocked when alignment_passed=False."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Bash", {"command": "echo 'hello' > /srv/project/app.py"}
        )
        assert decision == "deny"
        assert "ALIGNMENT GATE" in reason


# ---------------------------------------------------------------------------
# 2. Alignment gate allows code writes when alignment_passed=True
# ---------------------------------------------------------------------------

class TestAlignmentGateAllowing:
    """Code writes allowed when alignment_passed is True (falls through to other checks)."""

    def test_alignment_passed_allows_code_write(self, aligned_state, monkeypatch):
        """Write to .py file NOT blocked by alignment gate when alignment_passed=True."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        # Should hit the coordinator block (Issue #528), NOT the alignment gate
        if decision == "deny":
            assert "ALIGNMENT GATE" not in reason
            assert "WORKFLOW ENFORCEMENT" in reason


# ---------------------------------------------------------------------------
# 3. Non-code files not blocked by alignment gate
# ---------------------------------------------------------------------------

class TestAlignmentGateNonCodeFiles:
    """Non-code files should not be affected by alignment gate."""

    def test_alignment_not_passed_allows_non_code_file(self, unaligned_state, monkeypatch):
        """Write to README.md not blocked by alignment gate."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/README.md", "content": "# Hello"}
        )
        # Non-code file should pass through alignment gate
        if decision == "deny":
            assert "ALIGNMENT GATE" not in reason

    def test_alignment_not_passed_allows_json_file(self, unaligned_state, monkeypatch):
        """Write to .json file not blocked by alignment gate."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/config.json", "content": "{}"}
        )
        if decision == "deny":
            assert "ALIGNMENT GATE" not in reason


# ---------------------------------------------------------------------------
# 4. Read tools not affected by alignment gate
# ---------------------------------------------------------------------------

class TestAlignmentGateReadTools:
    """Read tools should never be blocked by alignment gate."""

    def test_alignment_not_passed_allows_read_tools(self, unaligned_state, monkeypatch):
        """Read tool not blocked regardless of alignment state."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Read", {"file_path": "/srv/project/app.py"}
        )
        assert decision == "allow"


# ---------------------------------------------------------------------------
# 5. Pipeline agents bypass alignment gate
# ---------------------------------------------------------------------------

class TestAlignmentGatePipelineAgents:
    """Pipeline agents should bypass alignment gate entirely."""

    def test_pipeline_agent_allowed_regardless(self, unaligned_state, monkeypatch):
        """Pipeline agent (implementer) allowed even without alignment."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        assert decision == "allow"
        assert "implementer" in reason.lower()


# ---------------------------------------------------------------------------
# 6. No pipeline active - alignment check not triggered
# ---------------------------------------------------------------------------

class TestAlignmentGateNoPipeline:
    """When no pipeline is active, alignment gate should not fire."""

    def test_no_pipeline_active_not_affected(self, monkeypatch):
        """Without active pipeline, alignment check is skipped entirely."""
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_state_585.json")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        # Should not get alignment gate denial when no pipeline active
        if decision == "deny":
            assert "ALIGNMENT GATE" not in reason


# ---------------------------------------------------------------------------
# 7. Missing/tampered state file
# ---------------------------------------------------------------------------

class TestAlignmentGateStateFileEdgeCases:
    """Edge cases for state file: missing, tampered."""

    def test_missing_state_file_fails_closed(self, monkeypatch):
        """No state file means _has_alignment_passed() returns False."""
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_alignment_585.json")
        assert hook._has_alignment_passed() is False

    def test_tampered_alignment_flag_detected(self, state_file, monkeypatch):
        """Modify alignment_passed in JSON without re-signing - HMAC mismatch returns False."""
        from pipeline_state import sign_state
        state = {
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-tampered-585",
            "explicitly_invoked": True,
            "alignment_passed": False,
        }
        signed = sign_state(state, "test-session")
        # Tamper: flip alignment_passed without re-signing
        signed["alignment_passed"] = True
        path = state_file(signed)
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._has_alignment_passed() is False

    def test_malformed_json_fails_closed(self, tmp_path, monkeypatch):
        """Malformed JSON in state file returns False."""
        bad_file = tmp_path / "bad_state.json"
        bad_file.write_text("{not valid json")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(bad_file))
        assert hook._has_alignment_passed() is False
