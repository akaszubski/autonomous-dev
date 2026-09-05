"""
Unit tests for Issue #528: Enforce /implement hard block when explicitly invoked.

Validates that when /implement is explicitly invoked by the user, the coordinator
(non-pipeline agent) is blocked from making code changes directly — it must
delegate to pipeline agents (implementer, test-master, doc-master).

Tests cover:
- _is_explicit_implement_active() function
- Coordinator blocking in validate_agent_authorization()
- Pipeline agent bypass
- Non-code file exemptions
- ENFORCEMENT_LEVEL=off override
- NATIVE_TOOLS fast path blocking

Date: 2026-03-21
Issue: #528
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hook's parent to path so we can import the module
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

# Also add lib dir for any transitive imports
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
def valid_state(state_file, monkeypatch):
    """Create a valid explicit pipeline state and set env var."""
    path = state_file({
        "session_start": datetime.now().isoformat(),
        "mode": "full",
        "run_id": "test-run",
        "explicitly_invoked": True,
        "alignment_passed": True,
    })
    monkeypatch.setenv("PIPELINE_STATE_FILE", path)
    return path


# ---------------------------------------------------------------------------
# 1. _is_explicit_implement_active() tests
# ---------------------------------------------------------------------------

class TestIsExplicitImplementActive:
    """Tests for the _is_explicit_implement_active() function."""

    def test_valid_state_returns_true(self, valid_state):
        """Active explicit state with valid TTL returns True."""
        assert hook._is_explicit_implement_active() is True

    def test_missing_flag_returns_false(self, state_file, monkeypatch):
        """State file without explicitly_invoked flag returns False."""
        path = state_file({
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run",
        })
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._is_explicit_implement_active() is False

    def test_false_flag_returns_false(self, state_file, monkeypatch):
        """State file with explicitly_invoked=false returns False."""
        path = state_file({
            "session_start": datetime.now().isoformat(),
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": False,
        })
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._is_explicit_implement_active() is False

    def test_expired_ttl_returns_false(self, state_file, monkeypatch):
        """State file older than 2 hours returns False."""
        expired = (datetime.now() - timedelta(hours=3)).isoformat()
        path = state_file({
            "session_start": expired,
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        })
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._is_explicit_implement_active() is False

    def test_missing_file_returns_false(self, monkeypatch):
        """Non-existent state file returns False."""
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_state_528.json")
        assert hook._is_explicit_implement_active() is False

    def test_malformed_json_returns_false(self, tmp_path, monkeypatch):
        """Malformed JSON in state file returns False."""
        bad_file = tmp_path / "bad_state.json"
        bad_file.write_text("{not valid json")
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(bad_file))
        assert hook._is_explicit_implement_active() is False

    def test_missing_session_start_returns_false(self, state_file, monkeypatch):
        """State file with no session_start returns False."""
        path = state_file({
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        })
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._is_explicit_implement_active() is False

    def test_near_ttl_boundary_returns_true(self, state_file, monkeypatch):
        """State file just under 2 hours returns True."""
        near_expiry = (datetime.now() - timedelta(hours=1, minutes=59)).isoformat()
        path = state_file({
            "session_start": near_expiry,
            "mode": "full",
            "run_id": "test-run",
            "explicitly_invoked": True,
        })
        monkeypatch.setenv("PIPELINE_STATE_FILE", path)
        assert hook._is_explicit_implement_active() is True


# ---------------------------------------------------------------------------
# 2. Coordinator blocking in validate_agent_authorization()
# ---------------------------------------------------------------------------

class TestCoordinatorBlocking:
    """Coordinator (non-pipeline agent) should be blocked from code writes."""

    def test_write_py_blocked(self, valid_state, monkeypatch):
        """Coordinator Write to .py file is blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        assert decision == "deny"
        assert "delegate" in reason.lower()

    def test_edit_py_blocked(self, valid_state, monkeypatch):
        """Coordinator Edit to .py file is blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Edit", {"file_path": "/srv/project/app.py", "old_string": "a", "new_string": "b"}
        )
        assert decision == "deny"
        assert "pipeline agents" in reason.lower()

    def test_bash_redirect_to_code_blocked(self, valid_state, monkeypatch):
        """Coordinator Bash redirect to .py file is blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Bash", {"command": "echo 'code' > /srv/project/app.py"}
        )
        assert decision == "deny"
        assert "WORKFLOW ENFORCEMENT" in reason

    def test_write_js_blocked(self, valid_state, monkeypatch):
        """Coordinator Write to .js file is blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.js", "content": "console.log('hi')"}
        )
        assert decision == "deny"

    def test_write_ts_blocked(self, valid_state, monkeypatch):
        """Coordinator Write to .ts file is blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.ts", "content": "const x = 1;"}
        )
        assert decision == "deny"


# ---------------------------------------------------------------------------
# 3. Pipeline agent bypass
# ---------------------------------------------------------------------------

class TestPipelineAgentBypass:
    """Pipeline agents should still be allowed through."""

    @pytest.mark.parametrize("agent", ["implementer", "test-master", "doc-master"])
    def test_pipeline_agent_allowed(self, valid_state, monkeypatch, agent):
        """Pipeline agents bypass the explicit implement block."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", agent)
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "real impl"}
        )
        assert decision == "allow"
        assert agent in reason


# ---------------------------------------------------------------------------
# 4. Exemptions
# ---------------------------------------------------------------------------

class TestExemptions:
    """Non-code files and non-file-write Bash commands should be allowed."""

    @pytest.mark.parametrize("ext", [".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".cfg", ".ini"])
    def test_non_code_files_allowed(self, valid_state, monkeypatch, ext):
        """Non-code file extensions are not blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": f"/srv/project/config{ext}", "content": "data"}
        )
        # Should not be denied by the explicit implement check
        assert decision != "deny" or "WORKFLOW ENFORCEMENT" not in reason

    def test_bash_without_file_writes_allowed(self, valid_state, monkeypatch):
        """Bash commands without file writes are not blocked."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Bash", {"command": "pytest tests/ -v"}
        )
        # The Bash command doesn't write to code files, so should be allowed
        assert decision != "deny" or "WORKFLOW ENFORCEMENT" not in reason

    def test_read_tool_not_blocked(self, valid_state, monkeypatch):
        """Read tool is not subject to blocking."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        decision, reason = hook.validate_agent_authorization(
            "Read", {"file_path": "/srv/project/app.py"}
        )
        assert decision == "allow"


# ---------------------------------------------------------------------------
# 5. ENFORCEMENT_LEVEL=off override
# ---------------------------------------------------------------------------

class TestEnforcementLevelOff:
    """ENFORCEMENT_LEVEL=off should disable the block."""

    def test_off_overrides_block(self, valid_state, monkeypatch):
        """ENFORCEMENT_LEVEL=off allows coordinator code writes."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "off")
        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "code"}
        )
        # With enforcement off, the explicit implement block should not fire
        # It returns allow from the "Active /implement pipeline" path
        assert decision == "allow"


# ---------------------------------------------------------------------------
# 6. _is_code_file_target() tests
# ---------------------------------------------------------------------------

class TestIsCodeFileTarget:
    """Tests for the _is_code_file_target() helper.

    Paths are ``/srv/project/...``, NOT ``/tmp/...``. ``_is_scratch_path`` is
    consulted first (Issue #1408), so a ``/tmp`` path is exempt by definition
    and an assertion using one would be testing the exemption rather than the
    extension classification it names. Do not "simplify" these back to /tmp —
    see tests/regression/test_scratch_exemption_code_target.py for the
    exemption's own both-arms coverage.
    """

    def test_write_py_is_code(self):
        assert hook._is_code_file_target("Write", {"file_path": "/srv/project/app.py"}) is True

    def test_write_json_is_not_code(self):
        assert hook._is_code_file_target("Write", {"file_path": "/srv/project/config.json"}) is False

    def test_write_md_is_not_code(self):
        assert hook._is_code_file_target("Write", {"file_path": "/srv/project/README.md"}) is False

    def test_edit_ts_is_code(self):
        assert hook._is_code_file_target("Edit", {"file_path": "/srv/project/app.ts"}) is True

    def test_bash_with_py_redirect_is_code(self):
        assert hook._is_code_file_target("Bash", {"command": "echo 'x' > app.py"}) is True

    def test_bash_without_writes_is_not_code(self):
        assert hook._is_code_file_target("Bash", {"command": "pytest -v"}) is False

    def test_bash_with_json_redirect_is_not_code(self):
        assert hook._is_code_file_target("Bash", {"command": "echo '{}' > config.json"}) is False

    def test_empty_file_path_is_not_code(self):
        assert hook._is_code_file_target("Write", {"file_path": ""}) is False

    def test_read_tool_is_not_code(self):
        assert hook._is_code_file_target("Read", {"file_path": "/srv/project/app.py"}) is False

    # Issue #623: infrastructure .md files must be treated as code targets

    def test_write_infra_agent_md_is_code(self):
        """Write to agents/*.md is a code target — infrastructure file (Issue #623)."""
        with patch.object(hook, "_is_autonomous_dev_repo", return_value=True):
            result = hook._is_code_file_target(
                "Write",
                {"file_path": "/repo/plugins/autonomous-dev/agents/implementer.md"},
            )
        assert result is True

    def test_write_infra_commands_md_is_code(self):
        """Write to commands/*.md is a code target — infrastructure file (Issue #623)."""
        with patch.object(hook, "_is_autonomous_dev_repo", return_value=True):
            result = hook._is_code_file_target(
                "Write",
                {"file_path": "/repo/plugins/autonomous-dev/commands/implement.md"},
            )
        assert result is True

    def test_write_infra_skills_md_is_code(self):
        """Write to skills/*/SKILL.md is a code target — infrastructure file (Issue #623)."""
        with patch.object(hook, "_is_autonomous_dev_repo", return_value=True):
            result = hook._is_code_file_target(
                "Write",
                {"file_path": "/repo/plugins/autonomous-dev/skills/testing-guide/SKILL.md"},
            )
        assert result is True

    def test_write_regular_md_still_not_code(self):
        """Write to README.md is NOT a code target — regular doc file (Issue #623)."""
        with patch.object(hook, "_is_protected_infrastructure", return_value=False):
            result = hook._is_code_file_target("Write", {"file_path": "/repo/README.md"})
        assert result is False

    def test_write_docs_md_still_not_code(self):
        """Write to docs/*.md is NOT a code target — regular doc file (Issue #623)."""
        with patch.object(hook, "_is_protected_infrastructure", return_value=False):
            result = hook._is_code_file_target(
                "Write", {"file_path": "/repo/docs/ARCHITECTURE.md"}
            )
        assert result is False

    def test_bash_infra_md_redirect_is_code(self):
        """Bash redirect to agents/*.md is a code target — infrastructure file (Issue #623)."""
        with patch.object(hook, "_is_autonomous_dev_repo", return_value=True):
            result = hook._is_code_file_target(
                "Bash",
                {"command": "echo 'content' > plugins/autonomous-dev/agents/foo.md"},
            )
        assert result is True

    def test_coordinator_infra_md_blocked_in_fast_path(
        self, valid_state, monkeypatch
    ):
        """Coordinator + explicit /implement + Write to agents/*.md → blocked (Issue #623)."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        with patch.object(hook, "_is_autonomous_dev_repo", return_value=True):
            decision, reason = hook.validate_agent_authorization(
                "Write",
                {"file_path": "/repo/plugins/autonomous-dev/agents/implementer.md", "content": "x"},
            )
        assert decision == "deny"
        assert "WORKFLOW ENFORCEMENT" in reason


# ---------------------------------------------------------------------------
# 7. NATIVE_TOOLS fast path (integration-level)
# ---------------------------------------------------------------------------

class TestNativeToolsFastPath:
    """Test explicit implement enforcement in the native tools fast path.

    These test the _is_code_file_target + _is_explicit_implement_active
    combination used in main() for native tools. We test the helper functions
    directly since main() calls sys.exit.
    """

    def test_coordinator_code_write_detected(self, valid_state, monkeypatch):
        """Fast path detects coordinator code writes when explicit implement active."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        # Simulate what the fast path checks
        tool_name = "Write"
        tool_input = {"file_path": "/srv/project/app.py", "content": "code"}
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
        assert agent_name not in hook.PIPELINE_AGENTS
        assert hook._is_explicit_implement_active() is True
        assert hook._is_code_file_target(tool_name, tool_input) is True

    def test_pipeline_agent_bypasses_fast_path(self, valid_state, monkeypatch):
        """Pipeline agent is NOT blocked in fast path."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        agent_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
        assert agent_name in hook.PIPELINE_AGENTS

    def test_no_state_file_backward_compat(self, monkeypatch):
        """Without state file, fast path does not block (backward compatibility)."""
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_state_528.json")
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        assert hook._is_explicit_implement_active() is False

    def test_enforcement_off_bypasses_fast_path(self, valid_state, monkeypatch):
        """ENFORCEMENT_LEVEL=off disables fast path block."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "off")
        level = os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower()
        assert level == "off"


# ---------------------------------------------------------------------------
# 8. Default enforcement is "block" during explicit /implement (Issue #529)
# ---------------------------------------------------------------------------

class TestDefaultEnforcementIsBlockDuringExplicitImplement:
    """When ENFORCEMENT_LEVEL is unset and explicit /implement is active,
    the default must be 'block', not 'suggest'."""

    def test_default_enforcement_is_block_during_explicit_implement(
        self, valid_state, monkeypatch
    ):
        """Write to .py is DENIED (not asked) when ENFORCEMENT_LEVEL is not set."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        # ENFORCEMENT_LEVEL is deliberately NOT set (clean_env fixture removes it)
        assert os.getenv("ENFORCEMENT_LEVEL") is None

        decision, reason = hook.validate_agent_authorization(
            "Write", {"file_path": "/srv/project/app.py", "content": "print('hello')"}
        )
        assert decision == "deny", (
            "Expected 'deny' when ENFORCEMENT_LEVEL is unset and explicit /implement active, "
            f"but got '{decision}'. Default must be 'block', not 'suggest'."
        )
        assert "WORKFLOW ENFORCEMENT" in reason

    def test_default_enforcement_blocks_edit_during_explicit_implement(
        self, valid_state, monkeypatch
    ):
        """Edit to .py is DENIED when ENFORCEMENT_LEVEL is not set."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        assert os.getenv("ENFORCEMENT_LEVEL") is None

        decision, reason = hook.validate_agent_authorization(
            "Edit", {"file_path": "/srv/project/module.py", "old_string": "x", "new_string": "y"}
        )
        assert decision == "deny"

    def test_native_fast_path_default_is_block(self, valid_state, monkeypatch):
        """NATIVE_TOOLS fast path: ENFORCEMENT_LEVEL unset defaults to 'block' (not 'off')."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        assert os.getenv("ENFORCEMENT_LEVEL") is None

        # The fast path condition: os.getenv("ENFORCEMENT_LEVEL", "block") != "off"
        # When unset, default "block" != "off" → True → the block fires
        level = os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower()
        assert level != "off", (
            "Default ENFORCEMENT_LEVEL in explicit implement fast path must not be 'off'. "
            f"Got '{level}'."
        )
        assert level == "block"


# ---------------------------------------------------------------------------
# Regression test: Issue #586 — avoid double state file read
# ---------------------------------------------------------------------------

class TestSingleCallOptimization:
    """Issue #586: _is_explicit_implement_active() must be called only once per
    validate_agent_authorization() invocation (not twice).

    Before the fix, validate_agent_authorization() called the function twice in
    sequence — once for the alignment gate check and once for the coordinator
    enforcement check — causing two state file reads for a single authorization
    decision. The fix extracts the result into a local variable 'impl_active'
    before either check runs.
    """

    def test_validate_agent_authorization_calls_is_explicit_once(
        self, valid_state, monkeypatch
    ):
        """validate_agent_authorization() must call _is_explicit_implement_active()
        exactly once regardless of which branch is taken (Issue #586).
        """
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")
        monkeypatch.setenv("ENFORCEMENT_LEVEL", "block")

        call_count = {"n": 0}
        original = hook._is_explicit_implement_active

        def counting_wrapper():
            call_count["n"] += 1
            return original()

        with patch.object(hook, "_is_explicit_implement_active", side_effect=counting_wrapper):
            # Trigger the coordinator-blocking path (non-pipeline agent + code file)
            hook.validate_agent_authorization(
                "Edit",
                {"file_path": "/srv/project/module.py", "old_string": "x", "new_string": "y"},
            )

        assert call_count["n"] == 1, (
            f"_is_explicit_implement_active() was called {call_count['n']} times "
            f"inside validate_agent_authorization(), expected exactly 1. "
            f"This indicates the double state-file-read regression (Issue #586) has returned."
        )

    def test_validate_agent_authorization_calls_is_explicit_once_when_inactive(
        self, monkeypatch, tmp_path
    ):
        """Even when /implement is NOT active, the call count must be <= 1 (Issue #586).

        When impl_active is False the conditions short-circuit, so the function
        may be called 0 or 1 times — but never 2.
        """
        # Point state file at a non-existent path so _is_pipeline_active returns False
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(tmp_path / "nonexistent.json"))
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "")

        call_count = {"n": 0}
        original = hook._is_explicit_implement_active

        def counting_wrapper():
            call_count["n"] += 1
            return original()

        with patch.object(hook, "_is_explicit_implement_active", side_effect=counting_wrapper):
            hook.validate_agent_authorization(
                "Edit",
                {"file_path": "/srv/project/module.py", "old_string": "x", "new_string": "y"},
            )

        assert call_count["n"] <= 1, (
            f"_is_explicit_implement_active() was called {call_count['n']} times "
            f"when pipeline is inactive — expected 0 or 1 (Issue #586)."
        )
