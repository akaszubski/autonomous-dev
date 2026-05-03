"""
Tests for cross-repo symlink write guard in unified_pre_tool.py (Issue #1019).

Validates that:
1. _is_cross_repo_protected_write correctly detects cross-repo symlink writes
2. Same-repo writes are allowed (no regression)
3. Write/Edit gate blocks cross-repo writes even when pipeline is active
4. Bash heredoc/redirect gate blocks cross-repo writes
5. Deny cache is populated on cross-repo block

Date: 2026-05-03
"""

import json
import os
import sys
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


@pytest.fixture()
def synthetic_repo_layout(tmp_path):
    """Build a synthetic two-repo layout with a symlink from consumer into canonical.

    Layout:
        tmp_path/
        ├── canonical/
        │   ├── .claude/commands/implement.md   (marker)
        │   └── plugins/autonomous-dev/lib/
        │       └── foo.py                       (protected file)
        └── consumer/
            ├── .claude/commands/implement.md   (marker)
            └── plugins -> ../canonical/plugins  (symlink)

    Yields:
        (canonical_root, consumer_root, real_foo, symlinked_foo)
        where real_foo is the canonical path and symlinked_foo is the path
        via consumer's symlinked plugins directory.
    """
    canonical = tmp_path / "canonical"
    consumer = tmp_path / "consumer"

    # Create canonical repo structure
    (canonical / ".claude" / "commands").mkdir(parents=True)
    (canonical / ".claude" / "commands" / "implement.md").touch()
    (canonical / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True)
    real_foo = canonical / "plugins" / "autonomous-dev" / "lib" / "foo.py"
    real_foo.write_text("# real\n")

    # Create consumer repo structure with symlink into canonical plugins
    (consumer / ".claude" / "commands").mkdir(parents=True)
    (consumer / ".claude" / "commands" / "implement.md").touch()
    # symlink: consumer/plugins -> ../canonical/plugins
    (consumer / "plugins").symlink_to(canonical / "plugins")

    symlinked_foo = consumer / "plugins" / "autonomous-dev" / "lib" / "foo.py"

    yield (canonical, consumer, real_foo, symlinked_foo)


# ---------------------------------------------------------------------------
# TestCrossRepoHelperDirect
# ---------------------------------------------------------------------------

class TestCrossRepoHelperDirect:
    """Direct tests for _is_cross_repo_protected_write helper."""

    def test_same_repo_edit_returns_false(self, synthetic_repo_layout, monkeypatch):
        """Writing to a canonical path from within the canonical repo should return (False, None)."""
        canonical_root, _, real_foo, _ = synthetic_repo_layout
        monkeypatch.chdir(canonical_root)
        result = hook._is_cross_repo_protected_write(str(real_foo))
        assert result == (False, None), f"Expected (False, None) but got {result}"

    def test_cross_repo_edit_via_symlink_returns_true(self, synthetic_repo_layout, monkeypatch):
        """Writing to a protected file via a consumer-side symlink should return (True, reason)."""
        canonical_root, consumer_root, _, symlinked_foo = synthetic_repo_layout
        monkeypatch.chdir(consumer_root)
        is_cross, reason = hook._is_cross_repo_protected_write(str(symlinked_foo))
        assert is_cross is True, f"Expected cross-repo=True but got {is_cross}"
        assert reason is not None
        assert str(canonical_root) in reason, f"Canonical root not in reason: {reason}"
        assert str(consumer_root) in reason, f"Consumer root not in reason: {reason}"

    def test_non_symlinked_path_returns_false_same_cwd(self, synthetic_repo_layout, monkeypatch):
        """Regular file path (no symlink) from canonical cwd returns (False, None)."""
        canonical_root, _, real_foo, _ = synthetic_repo_layout
        monkeypatch.chdir(canonical_root)
        result = hook._is_cross_repo_protected_write(str(real_foo))
        assert result == (False, None)

    def test_non_symlinked_path_from_unrelated_cwd_returns_false(
        self, synthetic_repo_layout, tmp_path, monkeypatch
    ):
        """From an unrelated cwd (no marker), fail-open: returns (False, None)."""
        _, _, real_foo, _ = synthetic_repo_layout
        unrelated_dir = tmp_path / "unrelated"
        unrelated_dir.mkdir()
        monkeypatch.chdir(unrelated_dir)
        # real_foo has no symlink, and unrelated_dir has no autonomous-dev marker
        result = hook._is_cross_repo_protected_write(str(real_foo))
        assert result == (False, None)

    def test_empty_path_returns_false(self, monkeypatch, tmp_path):
        """Empty file path returns (False, None) without raising."""
        monkeypatch.chdir(tmp_path)
        result = hook._is_cross_repo_protected_write("")
        assert result == (False, None)

    def test_reason_contains_cross_repo_message(self, synthetic_repo_layout, monkeypatch):
        """Reason string must mention 'Cross-repo symlink write detected'."""
        _, consumer_root, _, symlinked_foo = synthetic_repo_layout
        monkeypatch.chdir(consumer_root)
        is_cross, reason = hook._is_cross_repo_protected_write(str(symlinked_foo))
        assert is_cross is True
        assert "Cross-repo symlink write detected" in reason


# ---------------------------------------------------------------------------
# TestCrossRepoMainFlow
# ---------------------------------------------------------------------------

class TestCrossRepoMainFlow:
    """Integration tests: cross-repo writes blocked via main hook flow."""

    def _make_write_stdin(self, file_path: str) -> str:
        """Build a fake hook stdin JSON for a Write tool call."""
        return json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": file_path,
                "content": "# injected\n",
            },
        })

    def test_cross_repo_write_blocked_via_main_flow(
        self, synthetic_repo_layout, monkeypatch, capsys
    ):
        """Write via symlink from consumer cwd should produce deny decision."""
        _, consumer_root, _, symlinked_foo = synthetic_repo_layout
        monkeypatch.chdir(consumer_root)

        stdin_data = self._make_write_stdin(str(symlinked_foo))
        monkeypatch.setattr("sys.stdin", StringIO(stdin_data))

        # Pipeline active so the normal infra gate would allow — but cross-repo gate
        # must fire first regardless of pipeline state.
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: True)

        with pytest.raises(SystemExit):
            hook.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # output_decision produces hookSpecificOutput format
        hook_output = output.get("hookSpecificOutput", {})
        perm_decision = hook_output.get("permissionDecision", "")
        reason = hook_output.get("permissionDecisionReason", "")
        assert perm_decision == "deny", f"Expected deny, got: {output}"
        assert "Cross-repo symlink write detected" in reason, f"Unexpected reason: {reason}"

    def test_same_repo_write_not_blocked_by_cross_repo_gate(
        self, synthetic_repo_layout, monkeypatch, capsys
    ):
        """Write to canonical path from canonical cwd must not be blocked by cross-repo gate."""
        canonical_root, _, real_foo, _ = synthetic_repo_layout
        monkeypatch.chdir(canonical_root)

        stdin_data = self._make_write_stdin(str(real_foo))
        monkeypatch.setattr("sys.stdin", StringIO(stdin_data))

        # Pipeline active — normal infra gate should allow; cross-repo must not fire
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: True)

        # Should NOT raise SystemExit from the cross-repo gate (may exit via other paths)
        # We only care that if it exits, it is NOT due to cross-repo deny
        try:
            hook.main()
        except SystemExit:
            pass

        captured = capsys.readouterr()
        if captured.out.strip():
            try:
                decision = json.loads(captured.out)
                reason = decision.get("reason", "")
                assert "Cross-repo symlink write detected" not in reason, (
                    f"Same-repo write incorrectly blocked by cross-repo gate: {reason}"
                )
            except json.JSONDecodeError:
                pass  # Non-JSON output is fine (e.g., allow with no output)


# ---------------------------------------------------------------------------
# TestCrossRepoBashGate
# ---------------------------------------------------------------------------

class TestCrossRepoBashGate:
    """Tests for cross-repo block in the Bash heredoc/redirect gate."""

    def test_bash_heredoc_cross_repo_blocked(self, synthetic_repo_layout, monkeypatch):
        """Bash command with heredoc to symlinked protected path should return cross-repo reason."""
        _, consumer_root, _, symlinked_foo = synthetic_repo_layout
        monkeypatch.chdir(consumer_root)

        # Use the internal _check_bash_infra_writes helper directly
        command = f"cat > {symlinked_foo!s} <<EOF\nx\nEOF"
        result = hook._check_bash_infra_writes(command)
        # Result is (file_name, reason) when blocked, None when not blocked
        assert result is not None, "Expected Bash heredoc cross-repo write to be blocked"
        file_name, reason = result
        assert "Cross-repo symlink write detected" in reason, f"Unexpected reason: {reason}"


# ---------------------------------------------------------------------------
# TestDenyCacheRecordsCrossRepo
# ---------------------------------------------------------------------------

class TestDenyCacheRecordsCrossRepo:
    """Test that deny cache is populated when a cross-repo write is blocked."""

    def test_deny_cache_records_cross_repo_attempt(
        self, synthetic_repo_layout, monkeypatch, tmp_path, capsys
    ):
        """After a cross-repo block, deny cache must record the attempted path."""
        _, consumer_root, _, symlinked_foo = synthetic_repo_layout
        monkeypatch.chdir(consumer_root)

        # Redirect deny cache to a temp file for isolation
        temp_cache = str(tmp_path / "deny_cache.jsonl")
        monkeypatch.setattr(hook, "DENY_CACHE_PATH", temp_cache)

        # Build stdin for a Write call via the symlinked path
        stdin_data = json.dumps({
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(symlinked_foo),
                "content": "# injected\n",
            },
        })
        monkeypatch.setattr("sys.stdin", StringIO(stdin_data))
        monkeypatch.setattr(hook, "_is_pipeline_active", lambda: True)

        with pytest.raises(SystemExit):
            hook.main()

        # Check deny cache has a record for the symlinked path
        assert Path(temp_cache).exists(), "Deny cache file was not created"
        cache_content = Path(temp_cache).read_text()
        assert cache_content.strip(), "Deny cache is empty after cross-repo block"
        # Verify the path is in the cache
        assert hook._check_deny_cache(str(symlinked_foo)), (
            "Deny cache does not record the cross-repo blocked path"
        )
