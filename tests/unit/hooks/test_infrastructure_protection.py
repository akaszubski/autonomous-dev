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
        # Issue #1408: the tmp_path is not a git worktree, so the new
        # worktree-aware scoping would classify src/app.py as out-of-tree and
        # skip the gate. This test verifies the TIER gate fires on real
        # in-tree source, so stub the scoping to True. Out-of-tree/scratch
        # scoping is covered in tests/regression/test_issue_1408_write_gate_scoping.py.
        monkeypatch.setattr(hook, "_is_gated_repo_source", lambda _p: True)

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
        """Edit to install_manifest.json with implementer agent + active sentinel → allow."""
        monkeypatch.setenv("CLAUDE_AGENT_NAME", "implementer")

        # Activate agent_dispatch_sentinel (required since #1296 — defense-in-depth)
        from agent_dispatch_sentinel import write as _sentinel_write, clear as _sentinel_clear
        _sentinel_write("implementer")
        try:
            result = self._run_hook("Edit", {
                "file_path": "/Users/foo/Dev/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json",
                "old_string": "old",
                "new_string": "new",
            })

            decision = result["hookSpecificOutput"]["permissionDecision"]
            assert decision == "allow"
        finally:
            _sentinel_clear()


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
# Issue #1408 — git checkout / apply / patch to protected infra stays HARD.
# Direct-function tests (no _run_hook) so they do not depend on the pipeline
# state / network path exercised by the _run_hook-based tests above.
# ---------------------------------------------------------------------------


class TestGitCheckoutApplyInfraProtection:
    """_check_bash_infra_writes blocks git checkout/restore/apply/patch to infra."""

    def test_git_checkout_double_dash_lib_blocked(self, monkeypatch):
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(hook, "_is_protected_infrastructure", lambda _p: True)
        result = hook._check_bash_infra_writes(
            "git checkout -- plugins/autonomous-dev/lib/pipeline_state.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_git_restore_hooks_blocked(self, monkeypatch):
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(hook, "_is_protected_infrastructure", lambda _p: True)
        result = hook._check_bash_infra_writes(
            "git restore -- hooks/unified_pre_tool.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_git_apply_with_hooks_segment_blocked(self, monkeypatch):
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        result = hook._check_bash_infra_writes(
            "git apply /tmp/patch.diff  # modifies hooks/foo.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_patch_with_commands_segment_blocked(self, monkeypatch):
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        result = hook._check_bash_infra_writes(
            "patch commands/implement.md < /tmp/p.diff"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_git_checkout_branch_no_infra_allowed(self, monkeypatch):
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
        # Switching branches, no protected segment -> not blocked.
        assert hook._check_bash_infra_writes("git checkout main") is None


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


# ---------------------------------------------------------------------------
# TestToolIntentFallbackClassifiesByShape (Issue #1682)
# ---------------------------------------------------------------------------

class TestIssue1682FallbackClassifiesByShape:
    """The ``_ti_is_write`` fallback must classify by SHAPE, not by name.

    Regression for Issue #1682. ``_FALLBACK_WRITE_TOOLS`` enumerated the four
    NATIVE transports only, so with ``tool_intent`` unavailable every MCP
    write transport classified as a non-write and walked straight through the
    Issue #1435 protected-infrastructure hard floor that CLAUDE.md documents
    as holding for "any write-classified tool ... even under bypass".

    Measured before the fix, driving the real hook as a subprocess against a
    lib tree with ``tool_intent.py`` absent, targeting a protected path:
    ``Write``/``Edit`` denied; ``mcp__serena__replace_symbol_body``,
    ``mcp__serena__rename_symbol`` and a novel ``mcp__brandnew__write_file``
    all ALLOWED.

    The refusing arm and the permitting arm are BOTH exercised here: a
    fallback that denied everything would block ``Read``, which the module
    comment correctly calls catastrophic.
    """

    @pytest.fixture
    def no_tool_intent(self, monkeypatch):
        """Simulate tool_intent being unavailable (the import-failure fault)."""
        monkeypatch.setattr(hook, "_tool_intent", None)

    # --- arm 1: a registered MCP editor must be a write --------------------

    def test_mcp_editor_is_a_write_without_tool_intent(self, no_tool_intent):
        """mcp__serena__replace_symbol_body carries path + body -> WRITE."""
        assert hook._ti_is_write(
            "mcp__serena__replace_symbol_body",
            {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "name_path": "save",
                "body": "def save():\n    pass\n",
            },
        ) is True

    def test_mcp_replace_content_is_a_write_without_tool_intent(self, no_tool_intent):
        """replace_content carries its payload under ``repl``, not ``content``."""
        assert hook._ti_is_write(
            "mcp__serena__replace_content",
            {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "needle": "a",
                "repl": "b",
                "mode": "literal",
            },
        ) is True

    # --- arm 2: the catastrophic-regression control ------------------------

    def test_read_is_not_a_write_without_tool_intent(self, no_tool_intent):
        """Read carries a path and NO content -> must stay permitted."""
        assert hook._ti_is_write(
            "Read", {"file_path": "plugins/autonomous-dev/hooks/unified_pre_tool.py"}
        ) is False

    def test_grep_is_not_a_write_without_tool_intent(self, no_tool_intent):
        """Grep carries ``path`` -- the conjunction is what keeps it a read."""
        assert hook._ti_is_write(
            "Grep", {"pattern": "def", "path": "plugins/autonomous-dev/lib"}
        ) is False

    def test_readonly_mcp_tool_with_a_path_is_not_a_write(self, no_tool_intent):
        """find_symbol carries ``relative_path`` but no content argument."""
        assert hook._ti_is_write(
            "mcp__serena__find_symbol",
            {"name_path": "foo", "relative_path": "plugins/autonomous-dev/lib/x.py"},
        ) is False

    # --- arm 3: negative control of a DIFFERENT shape ----------------------

    def test_mcp_tool_with_no_write_shaped_input_is_not_a_write(self, no_tool_intent):
        """An mcp__* tool with no path key at all must be permitted.

        Discriminating on the ``mcp__`` prefix rather than on input shape
        would refuse this; it must not.
        """
        assert hook._ti_is_write(
            "mcp__someserver__list_things", {"query": "x"}
        ) is False

    def test_content_without_a_path_is_not_a_filesystem_write(self, no_tool_intent):
        """A ``body`` with no path key (send-mail shape) is not a file write."""
        assert hook._ti_is_write(
            "mcp__ms365__send-mail", {"to": "a@b.c", "body": "hello"}
        ) is False

    # --- arm 4: the arm an ALLOWLIST fix fails -----------------------------

    def test_novel_never_enumerated_writer_is_a_write(self, no_tool_intent):
        """A tool name absent from every registry, carrying path + content.

        Adding MCP editor names to ``_FALLBACK_WRITE_TOOLS`` would pass every
        other test in this class and fail this one -- which is the whole
        point: an allowlist moves the hole to the next unenumerated writer.
        """
        assert hook._ti_is_write(
            "mcp__brandnew__write_file",
            {"path": "plugins/autonomous-dev/hooks/unified_pre_tool.py",
             "content": "x = 1\n"},
        ) is True

    def test_novel_writer_under_a_different_path_key(self, no_tool_intent):
        """Same class, different member: ``file_path`` + ``new_string``."""
        assert hook._ti_is_write(
            "mcp__unheardof__patch_file",
            {"file_path": "/repo/lib/a.py", "new_string": "y = 2\n"},
        ) is True

    # --- the native transports must not regress ----------------------------

    @pytest.mark.parametrize("tool_name", list(hook._FALLBACK_WRITE_TOOLS))
    def test_native_write_tools_still_classify_as_writes(self, tool_name, no_tool_intent):
        """MultiEdit has no top-level content key, so the tuple still earns its keep."""
        assert hook._ti_is_write(tool_name, {}) is True

    # --- the healthy path must be unchanged --------------------------------

    def test_healthy_path_delegates_to_is_write_unchanged(self, monkeypatch):
        """With tool_intent healthy, ``is_write`` decides and nothing else runs."""
        calls = []

        class _Healthy:
            @staticmethod
            def is_write(tool_name, tool_input):
                calls.append((tool_name, tool_input))
                return False

            @staticmethod
            def classify(tool_name, tool_input):  # must NOT be consulted
                raise AssertionError("classify consulted while is_write works")

        monkeypatch.setattr(hook, "_tool_intent", _Healthy)
        # Write-shaped input that the SHAPE rule would call a write: the
        # healthy verdict must win, proving no second path was introduced.
        assert hook._ti_is_write(
            "mcp__serena__replace_content",
            {"relative_path": "a.py", "repl": "b"},
        ) is False
        assert len(calls) == 1

    def test_stale_install_falls_back_to_classify(self, monkeypatch):
        """A stale install exposing classify but not is_write (the #1471 shape).

        This rung is load-bearing for the content-less writers -- rename_symbol
        and delete_lines carry no content key, so no shape test can see them,
        but tool_intent's MCP_WRITE_TOOLS registry still can.
        """
        class _Stale:
            @staticmethod
            def classify(tool_name, tool_input):
                return "WRITE" if tool_name.endswith("rename_symbol") else "READ"

        monkeypatch.setattr(hook, "_tool_intent", _Stale)
        assert not hasattr(_Stale, "is_write")
        assert hook._ti_is_write(
            "mcp__serena__rename_symbol",
            {"relative_path": "lib/a.py", "name_path": "f", "new_name": "g"},
        ) is True
        assert hook._ti_is_write(
            "mcp__serena__find_symbol", {"relative_path": "lib/a.py"}
        ) is False


# ---------------------------------------------------------------------------
# Issue #1682: the fallback key sets must not drift from the canonical ones
# ---------------------------------------------------------------------------


class TestIssue1682FallbackKeySetsMatchCanonical:
    """``_FALLBACK_*_KEYS`` must stay identical to ``tool_intent``'s registries.

    The duplication is structurally necessary and cannot be removed: the
    fallback exists precisely for the moment ``tool_intent`` cannot be
    imported, so it cannot reference the canonical constants at that moment.
    What CAN be removed is the silence. ``tool_intent.py`` names its registries
    as the intended extension point, so an author adding a content key there
    and not to the hook copy would silently reintroduce the #1682 hole --
    an unenumerated MCP writer using the new key walking through the #1435
    protected-infrastructure hard floor whenever the library is unavailable.

    These two assertions are the enforcement that keeps one mechanism from
    having two divergent copies.
    """

    def test_fallback_path_keys_match_tool_intent(self):
        """The hook's PATH-key copy equals tool_intent.PATH_KEYS."""
        import tool_intent

        assert hook._FALLBACK_PATH_KEYS == tool_intent.PATH_KEYS, (
            "Issue #1682 drift: the fallback PATH-key copy has diverged from "
            "the canonical registry.\n"
            f"  canonical  tool_intent.PATH_KEYS      = {tool_intent.PATH_KEYS}\n"
            f"             plugins/autonomous-dev/lib/tool_intent.py\n"
            f"  hook copy  _FALLBACK_PATH_KEYS        = {hook._FALLBACK_PATH_KEYS}\n"
            f"             plugins/autonomous-dev/hooks/unified_pre_tool.py\n"
            "EDIT THE HOOK COPY to match tool_intent.py. tool_intent.py is the "
            "canonical registry and the intended extension point; the hook copy "
            "exists only because the fallback runs when tool_intent cannot be "
            "imported, so it must be updated in the same change."
        )

    def test_fallback_content_keys_match_tool_intent(self):
        """The hook's CONTENT-key copy equals tool_intent.CONTENT_KEYS."""
        import tool_intent

        assert hook._FALLBACK_CONTENT_KEYS == tool_intent.CONTENT_KEYS, (
            "Issue #1682 drift: the fallback CONTENT-key copy has diverged from "
            "the canonical registry.\n"
            f"  canonical  tool_intent.CONTENT_KEYS   = {tool_intent.CONTENT_KEYS}\n"
            f"             plugins/autonomous-dev/lib/tool_intent.py\n"
            f"  hook copy  _FALLBACK_CONTENT_KEYS     = {hook._FALLBACK_CONTENT_KEYS}\n"
            f"             plugins/autonomous-dev/hooks/unified_pre_tool.py\n"
            "EDIT THE HOOK COPY to match tool_intent.py. tool_intent.py is the "
            "canonical registry and the intended extension point; the hook copy "
            "exists only because the fallback runs when tool_intent cannot be "
            "imported, so it must be updated in the same change."
        )
