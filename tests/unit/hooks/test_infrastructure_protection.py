"""
Tests for infrastructure file protection in unified_pre_tool.py (Issue #483).

Validates that:
1. _is_protected_infrastructure correctly identifies protected files
2. _is_pipeline_active detects pipeline via agent name and state file
3. Main flow blocks direct edits to infrastructure files outside pipeline
4. output_decision supports systemMessage

Date: 2026-03-18
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# TestIsProtectedInfrastructure
# ---------------------------------------------------------------------------

class TestIsProtectedInfrastructure:
    """Tests for _is_protected_infrastructure helper."""

    def test_agents_md_file(self):
        assert hook._is_protected_infrastructure("agents/implementer.md") is True

    def test_agents_md_with_claude_prefix(self):
        assert hook._is_protected_infrastructure(".claude/agents/implementer.md") is True

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_agents_md_full_path(self, _mock):
        assert hook._is_protected_infrastructure(
            "/Users/foo/.claude/agents/implementer.md"
        ) is True

    def test_agents_md_plugin_path(self):
        assert hook._is_protected_infrastructure(
            "plugins/autonomous-dev/agents/implementer.md"
        ) is True

    def test_commands_md(self):
        assert hook._is_protected_infrastructure("commands/implement.md") is True

    def test_hooks_py(self):
        assert hook._is_protected_infrastructure("hooks/unified_pre_tool.py") is True

    def test_lib_py(self):
        assert hook._is_protected_infrastructure("lib/pipeline_state.py") is True

    def test_skills_md(self):
        assert hook._is_protected_infrastructure("skills/testing-guide/SKILL.md") is True

    def test_readme_not_protected(self):
        assert hook._is_protected_infrastructure("README.md") is False

    def test_src_app_not_protected(self):
        assert hook._is_protected_infrastructure("src/app.py") is False

    def test_test_file_not_protected(self):
        assert hook._is_protected_infrastructure("tests/test_foo.py") is False

    def test_agents_json_not_protected(self):
        """JSON in agents/ is not protected (wrong extension)."""
        assert hook._is_protected_infrastructure("agents/config.json") is False

    def test_hooks_md_not_protected(self):
        """Markdown in hooks/ is not protected (wrong extension for hooks/)."""
        assert hook._is_protected_infrastructure("hooks/readme.md") is False

    def test_lib_json_not_protected(self):
        """JSON in lib/ is not protected (wrong extension for lib/)."""
        assert hook._is_protected_infrastructure("lib/data.json") is False

    def test_empty_string(self):
        assert hook._is_protected_infrastructure("") is False

    def test_backslash_paths_normalized(self):
        """Windows-style backslash paths should still match."""
        assert hook._is_protected_infrastructure(
            "C:\\Users\\foo\\.claude\\agents\\implementer.md"
        ) is True


# ---------------------------------------------------------------------------
# TestIsPipelineActive
# ---------------------------------------------------------------------------

class TestIsPipelineActive:
    """Tests for _is_pipeline_active helper."""

    def test_implementer_agent(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")
        assert hook._is_pipeline_active() is True

    def test_test_master_agent(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "test-master")
        assert hook._is_pipeline_active() is True

    def test_doc_master_agent(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "doc-master")
        assert hook._is_pipeline_active() is True

    def test_reviewer_not_pipeline(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "reviewer")
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")
        assert hook._is_pipeline_active() is False

    def test_no_env_var(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        # Also ensure no state file
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")
        assert hook._is_pipeline_active() is False

    def test_valid_state_file(self, monkeypatch):
        """Pipeline state file < 2 hours old should activate."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            state = {"session_start": datetime.now().isoformat()}
            json.dump(state, f)
            f.flush()
            monkeypatch.setenv("PIPELINE_STATE_FILE", f.name)
            assert hook._is_pipeline_active() is True
        os.unlink(f.name)

    def test_stale_state_file(self, monkeypatch):
        """Pipeline state file with mtime > 30 min old should not activate.

        Issue #636 changed _is_pipeline_active() to use file mtime (30-min TTL)
        instead of session_start JSON field. Set mtime to 31+ minutes ago.
        """
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            old_time = datetime.now() - timedelta(hours=3)
            state = {"session_start": old_time.isoformat()}
            json.dump(state, f)
            f.flush()
            # Set file mtime to 31 minutes ago so mtime-based staleness check triggers
            import time
            stale_time = time.time() - (31 * 60)
            os.utime(f.name, (stale_time, stale_time))
            monkeypatch.setenv("PIPELINE_STATE_FILE", f.name)
            assert hook._is_pipeline_active() is False
        os.unlink(f.name)

    def test_missing_state_file(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/definitely_does_not_exist_12345.json")
        assert hook._is_pipeline_active() is False


# ---------------------------------------------------------------------------
# TestInfraProtectionInMainFlow
# ---------------------------------------------------------------------------

class TestInfraProtectionInMainFlow:
    """Integration tests for infrastructure protection in main() flow."""

    def _run_hook(self, tool_name: str, tool_input: dict) -> dict:
        """Run the hook's main() with given input and capture JSON output."""
        input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        captured = StringIO()

        with patch("sys.stdin", StringIO(input_data)), \
             patch("sys.stdout", captured), \
             pytest.raises(SystemExit):
            hook.main()

        output_text = captured.getvalue().strip()
        # May have multiple lines; take the last JSON line
        lines = [l for l in output_text.split("\n") if l.strip()]
        return json.loads(lines[-1]) if lines else {}

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_write_agents_no_pipeline_denied(self, _mock, monkeypatch):
        """Write to agents/foo.md without pipeline should be denied."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Write", {"file_path": "/home/user/.claude/agents/foo.md", "content": "test"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "systemMessage" in result

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_edit_hooks_no_pipeline_denied(self, _mock, monkeypatch):
        """Edit to hooks/bar.py without pipeline should be denied."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Edit", {
            "file_path": "/home/user/.claude/hooks/bar.py",
            "old_string": "old",
            "new_string": "new",
        })

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_write_agents_with_pipeline_agent_allowed(self, monkeypatch):
        """Write to agents/foo.md with implementer agent should be allowed."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        result = self._run_hook("Write", {"file_path": "/home/user/.claude/agents/foo.md", "content": "test"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_write_agents_with_state_file_allowed(self, monkeypatch):
        """Write to agents/foo.md with valid state file should be allowed."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            state = {"session_start": datetime.now().isoformat()}
            json.dump(state, f)
            f.flush()
            monkeypatch.setenv("PIPELINE_STATE_FILE", f.name)

            result = self._run_hook("Write", {"file_path": "/home/user/.claude/agents/foo.md", "content": "test"})

            decision = result["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow"
        os.unlink(f.name)

    def test_write_src_not_protected(self, monkeypatch, tmp_path):
        """Write to src/app.py should be allowed because src/ is NOT
        infrastructure-protected (test isolates the infrastructure-protection
        check from the orthogonal default-on Write/Edit gate).

        Issue #1142 Phase 1 flipped the Write/Edit gate to default-on, so
        ``src/app.py`` (a .py code file) now triggers that gate too. To preserve
        this test's ORIGINAL semantic intent — "src/ is not in the protected
        infrastructure list" — we create a ``.claude/.bypass`` marker in
        tmp_path. The universal bypass short-circuits the write-pipeline-gate
        but is unrelated to infrastructure-protection, so this test isolates
        the infrastructure-protection check in its original form.

        For the parallel test of the tier-aware gate behavior, see
        ``test_write_src_blocked_by_tier_gate`` below.
        """
        bypass_dir = tmp_path / ".claude"
        bypass_dir.mkdir()
        (bypass_dir / ".bypass").write_text("")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Write", {"file_path": "src/app.py", "content": "test"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_write_src_blocked_by_tier_gate(self, monkeypatch, tmp_path):
        """Write to src/app.py is blocked by the default-on tier-aware
        Write/Edit gate when no ``.claude/.bypass`` marker is present
        (Issue #1142 Phase 1 polarity flip).

        Parallel test for the new default-on gate behavior. Complements
        ``test_write_src_not_protected`` which verifies that src/ is NOT
        infrastructure-protected (separate orthogonal check).
        """
        # No .claude/.bypass marker. No pipeline active.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook(
            "Write",
            {
                "file_path": "src/app.py",
                "content": (
                    "def new_feature(data: list) -> dict:\n"
                    "    return {item: process(item) for item in data}\n"
                ),
            },
        )

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", (
            f"Write to src/app.py without .bypass marker should be denied by "
            f"the default-on tier-aware gate, got '{decision}'."
        )
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "/implement" in reason, (
            f"Expected '/implement' directive in reason, got: {reason}"
        )

    def test_read_agents_allowed(self, monkeypatch):
        """Read from agents/foo.md should be allowed (Read not blocked)."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Read", {"file_path": "/home/user/.claude/agents/foo.md"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


# ---------------------------------------------------------------------------
# TestOutputDecisionSystemMessage
# ---------------------------------------------------------------------------

class TestOutputDecisionSystemMessage:
    """Tests for output_decision with system_message support."""

    def test_with_system_message(self):
        captured = StringIO()
        with patch("sys.stdout", captured):
            hook.output_decision("deny", "blocked", system_message="You need /implement")

        result = json.loads(captured.getvalue())
        assert result["systemMessage"] == "You need /implement"
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_without_system_message(self):
        captured = StringIO()
        with patch("sys.stdout", captured):
            hook.output_decision("allow", "ok")

        result = json.loads(captured.getvalue())
        assert "systemMessage" not in result
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_empty_system_message_omitted(self):
        captured = StringIO()
        with patch("sys.stdout", captured):
            hook.output_decision("allow", "ok", system_message="")

        result = json.loads(captured.getvalue())
        assert "systemMessage" not in result


# ---------------------------------------------------------------------------
# TestInstallManifestProtection (Issue #980)
# ---------------------------------------------------------------------------


class TestInstallManifestProtection:
    """Tests for per-file protection of install_manifest.json (Issue #980).

    The deployment manifest at
    plugins/autonomous-dev/config/install_manifest.json MUST NOT be
    direct-edited by the coordinator — it requires the implementer agent
    (pipeline-active) so STEP 11 test-gate re-validation runs.
    """

    def _run_hook(self, tool_name: str, tool_input: dict) -> dict:
        """Run the hook's main() with given input and capture JSON output."""
        input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        captured = StringIO()

        with patch("sys.stdin", StringIO(input_data)), \
             patch("sys.stdout", captured), \
             pytest.raises(SystemExit):
            hook.main()

        output_text = captured.getvalue().strip()
        lines = [l for l in output_text.split("\n") if l.strip()]
        return json.loads(lines[-1]) if lines else {}

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_protected_absolute_path(self, _mock):
        """Absolute path to install_manifest.json → protected (True)."""
        assert hook._is_protected_infrastructure(
            "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json"
        ) is True

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_protected_relative_path(self, _mock):
        """Relative path 'plugins/autonomous-dev/config/install_manifest.json'
        → protected (True). The bare-relative form must match too."""
        assert hook._is_protected_infrastructure(
            "plugins/autonomous-dev/config/install_manifest.json"
        ) is True

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_basename_alone_not_matched(self, _mock):
        """Bare 'install_manifest.json' (no prefix) MUST NOT match —
        protection is path-prefixed, not basename-based."""
        assert hook._is_protected_infrastructure("install_manifest.json") is False

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_partial_basename_not_matched(self, _mock):
        """Partial-basename false positives MUST NOT match.

        - 'foo_install_manifest.json' must NOT match (different file)
        - 'install_manifest.json.bak' must NOT match (different file)
        """
        assert hook._is_protected_infrastructure(
            "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/foo_install_manifest.json"
        ) is False
        assert hook._is_protected_infrastructure(
            "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json.bak"
        ) is False

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_blocks_direct_edit_outside_pipeline(self, _mock, monkeypatch):
        """Edit attempt to install_manifest.json outside the pipeline → deny."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Edit", {
            "file_path": "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json",
            "old_string": "old",
            "new_string": "new",
        })

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_install_manifest_allows_edit_inside_pipeline(self, _mock, monkeypatch):
        """Edit to install_manifest.json with implementer agent → allow."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        result = self._run_hook("Edit", {
            "file_path": "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json",
            "old_string": "old",
            "new_string": "new",
        })

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


# ---------------------------------------------------------------------------
# TestBashInfrastructureProtection (#502)
# ---------------------------------------------------------------------------

class TestBashInfrastructureProtection:
    """Tests for Bash command inspection blocking writes to protected paths."""

    def _run_hook(self, tool_name: str, tool_input: dict) -> dict:
        """Run the hook's main() with given input and capture JSON output."""
        input_data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        captured = StringIO()

        with patch("sys.stdin", StringIO(input_data)), \
             patch("sys.stdout", captured), \
             pytest.raises(SystemExit):
            hook.main()

        output_text = captured.getvalue().strip()
        lines = [l for l in output_text.split("\n") if l.strip()]
        return json.loads(lines[-1]) if lines else {}

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_sed_inplace_to_protected_path_blocked(self, _mock, monkeypatch):
        """sed -i to agents/*.md should be blocked when pipeline not active."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "sed -i 's/old/new/g' /home/user/.claude/agents/foo.md"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_redirect_to_protected_path_blocked(self, _mock, monkeypatch):
        """Shell redirect (>) to hooks/*.py should be blocked."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "echo 'code' > /home/user/.claude/hooks/my_hook.py"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_tee_to_protected_path_blocked(self, _mock, monkeypatch):
        """tee to lib/*.py should be blocked."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "cat file.py | tee /home/user/.claude/lib/pipeline.py"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_cp_to_protected_path_blocked(self, _mock, monkeypatch):
        """cp to commands/*.md should be blocked."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "cp /tmp/new.md /home/user/.claude/commands/implement.md"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "BLOCKED" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_read_only_commands_allowed(self, monkeypatch):
        """Read-only Bash commands (cat, ls, grep) should be allowed."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "cat /home/user/.claude/agents/foo.md"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_bash_write_to_non_protected_path_allowed(self, monkeypatch):
        """Bash writes to non-protected paths (src/, tmp/) should be allowed."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "echo 'test' > /tmp/output.txt"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_bash_write_to_protected_path_allowed_when_pipeline_active(self, _mock, monkeypatch):
        """Bash writes to protected paths should be allowed when pipeline is active."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        result = self._run_hook("Bash", {"command": "sed -i 's/old/new/g' /home/user/.claude/agents/foo.md"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_bash_pytest_command_not_blocked(self, monkeypatch):
        """pytest commands should never be blocked (not writing to protected paths)."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")

        result = self._run_hook("Bash", {"command": "python -m pytest tests/ -x -q"})

        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


# ---------------------------------------------------------------------------
# Regression: Issue #504 — session_id "unknown" in PreToolUse log entries
# ---------------------------------------------------------------------------

class TestSessionIdFromStdin:
    """Regression tests for Issue #504: session_id extracted from hook stdin.

    Before the fix, _log_deviation() and _log_pretool_activity() only used
    os.getenv("CLAUDE_SESSION_ID", "unknown"), which is absent in most hook
    contexts. The fix stores the session_id from stdin input_data at module
    level so logging functions can fall back to it.
    """

    def test_session_id_from_stdin_when_env_absent(self, monkeypatch, tmp_path):
        """When CLAUDE_SESSION_ID env var is absent, log entries use session_id from stdin."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        # Set module-level _session_id as main() would after parsing stdin
        hook._session_id = "session-from-stdin-abc123"

        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True)

        # Patch os.getcwd so _log_deviation writes to our temp dir
        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))

        hook._log_deviation("test_file.py", "Write", "test reason")

        log_file = log_dir / "deviations.jsonl"
        assert log_file.exists(), "deviations.jsonl should have been created"
        entry = json.loads(log_file.read_text().strip())
        assert entry["session_id"] == "session-from-stdin-abc123"

    def test_session_id_env_var_takes_precedence(self, monkeypatch, tmp_path):
        """When CLAUDE_SESSION_ID env var IS set, it takes precedence over stdin value."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-xyz")
        hook._session_id = "session-from-stdin-abc123"

        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))

        hook._log_deviation("test_file.py", "Write", "test reason")

        log_file = log_dir / "deviations.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["session_id"] == "env-session-xyz"

    def test_pretool_activity_uses_stdin_session_id(self, monkeypatch, tmp_path):
        """_log_pretool_activity also uses the stdin session_id fallback."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        hook._session_id = "pretool-session-456"

        log_dir = tmp_path / ".claude" / "logs" / "activity"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))

        hook._log_pretool_activity("Bash", {"command": "ls"}, "allow", "test")

        # Find the log file (named by date)
        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1, f"Expected 1 activity log file, got {len(log_files)}"
        entry = json.loads(log_files[0].read_text().strip())
        assert entry["session_id"] == "pretool-session-456"

    def test_pretool_activity_env_takes_precedence(self, monkeypatch, tmp_path):
        """_log_pretool_activity prefers env var over stdin value."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-pretool-789")
        hook._session_id = "pretool-session-456"

        log_dir = tmp_path / ".claude" / "logs" / "activity"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(os, "getcwd", lambda: str(tmp_path))

        hook._log_pretool_activity("Bash", {"command": "ls"}, "allow", "test")

        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        entry = json.loads(log_files[0].read_text().strip())
        assert entry["session_id"] == "env-pretool-789"

    def test_module_default_is_unknown(self):
        """Module-level _session_id defaults to 'unknown' before main() runs."""
        # Reset to default
        hook._session_id = "unknown"
        assert hook._session_id == "unknown"


# ---------------------------------------------------------------------------
# TestToolIntentMigration — Issue #971
# ---------------------------------------------------------------------------


class TestToolIntentMigration:
    """Validate that ``_check_bash_infra_writes`` continues to catch existing
    infrastructure-protection scenarios after the Issue #971 migration.

    These tests confirm:
    1. The ``_extract_bash_file_writes`` shim returns the same shape as before.
    2. ``_check_bash_infra_writes`` still blocks each protected-path scenario.
    3. The fallback path (``_extract_bash_file_writes_legacy``) is preserved
       and reachable.
    4. The new ``_tool_intent`` module loads correctly when present.
    """

    def test_tool_intent_module_loaded(self):
        """The new tool_intent module should be importable from the hook."""
        assert hook._tool_intent is not None, (
            "tool_intent module failed to load — hook will fall back to "
            "legacy regex implementation. This is allowed but unexpected."
        )

    def test_legacy_implementation_preserved(self):
        """The legacy regex implementation must remain callable as fallback."""
        assert hasattr(hook, "_extract_bash_file_writes_legacy")
        # Smoke test: legacy still extracts targets from a simple redirect.
        targets = hook._extract_bash_file_writes_legacy("echo hi > /tmp/x")
        assert "/tmp/x" in targets

    def test_shim_matches_legacy_for_simple_redirect(self):
        """The shim must extract the same write targets as the legacy fn for
        a basic redirect — no behavioural regression on common cases."""
        cmd = "echo hi > /tmp/output.txt"
        shim_targets = hook._extract_bash_file_writes(cmd)
        legacy_targets = hook._extract_bash_file_writes_legacy(cmd)
        assert "/tmp/output.txt" in shim_targets
        assert "/tmp/output.txt" in legacy_targets

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_check_bash_infra_writes_blocks_sed_to_protected(self, _mock, monkeypatch):
        """sed -i to a protected path is still caught post-migration."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")
        cmd = "sed -i 's/foo/bar/' /home/user/.claude/agents/foo.md"
        result = hook._check_bash_infra_writes(cmd)
        assert result is not None, (
            f"_check_bash_infra_writes failed to block sed -i to protected path. "
            f"Migration to tool_intent regressed infrastructure protection."
        )
        file_name, reason = result
        assert "foo.md" in file_name
        assert "BLOCKED" in reason

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_check_bash_infra_writes_blocks_python_dump_to_agent(self, _mock, monkeypatch):
        """python -c writing to an agent file is still caught post-migration."""
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")
        cmd = (
            'python3 -c "from pathlib import Path; '
            "Path('/home/user/.claude/agents/foo.md').write_text('x')\""
        )
        result = hook._check_bash_infra_writes(cmd)
        assert result is not None
        file_name, reason = result
        assert "foo.md" in file_name
        assert "BLOCKED" in reason

    @patch.object(hook, "_is_autonomous_dev_repo", return_value=True)
    def test_check_bash_infra_writes_passes_python_read_of_agent(self, _mock, monkeypatch):
        """python -c READING an agent file (json.load / read_text) MUST NOT block.

        This is the canonical Issue #971 false-positive fix — the legacy
        regex flagged ``open(...)`` indiscriminately.
        """
        monkeypatch.delenv("CLAUDE_AGENT_NAME", raising=False)
        monkeypatch.setenv("PIPELINE_STATE_FILE", "/tmp/nonexistent_test_state.json")
        cmd = (
            'python3 -c "from pathlib import Path; '
            "print(Path('/home/user/.claude/agents/implementer.md').read_text())\""
        )
        result = hook._check_bash_infra_writes(cmd)
        assert result is None, (
            f"_check_bash_infra_writes incorrectly blocked a READ operation. "
            f"Issue #971 false-positive regression."
        )
