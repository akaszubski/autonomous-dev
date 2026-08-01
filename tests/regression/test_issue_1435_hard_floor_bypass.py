"""Regression tests for Issue #1435 — hard-floor infrastructure protection
must survive the universal hook bypass.

Before #1435 the universal bypass block in ``unified_pre_tool.py`` fired an
unconditional ``output_decision("allow", ...)`` BEFORE the protected-
infrastructure Write/Edit deny gate. So a session with ``.claude/.bypass`` (or
``AUTONOMOUS_DEV_BYPASS=1``) could silently rewrite the enforcement infra —
``hooks/*.py``, ``lib/*.py``, ``agents/*.md``, ``commands/*.md``,
``skills/*/SKILL.md``. ``_is_protected_infrastructure`` is a registered hard-
floor function (``config/hard_floor_hooks.json``), which is supposed to "always
fire". This module proves the post-fix invariant:

- Under bypass, Write/Edit to a protected-infra path is DENIED.
- Under bypass, Write/Edit to a NON-protected path (docs/, etc.) is still
  ALLOWED (bypass otherwise intact — positive control).
- Under bypass, a Bash command is still ALLOWED (bypass otherwise intact).

End-to-end tests invoke ``unified_pre_tool.py`` as a subprocess with controlled
stdin and env — the same way Claude Code calls the hook. Every deny-expecting
test creates ``.claude/commands/implement.md`` in its project dir because
``_is_protected_infrastructure`` only fires inside an autonomous-dev repo,
detected by that marker file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — import the bypass library and unified hook from the repo
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"
LIB_DIR = PLUGIN_ROOT / "lib"
HOOK_DIR = PLUGIN_ROOT / "hooks"
UNIFIED_PRE_TOOL = HOOK_DIR / "unified_pre_tool.py"

for _path in (str(LIB_DIR), str(HOOK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import hook_bypass  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors tests/regression/test_universal_hook_bypass.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bypass_env(monkeypatch):
    """Ensure the bypass env var is unset for every test by default."""
    monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create an isolated project root with a ``.claude/`` subdir."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _mark_autonomous_dev_repo(project_dir: Path) -> None:
    """Write ``.claude/commands/implement.md`` so ``_is_autonomous_dev_repo``
    (and therefore ``_is_protected_infrastructure``) recognizes this project
    as an autonomous-dev repo where infra protection applies.
    """
    commands_dir = project_dir / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    (commands_dir / "implement.md").write_text("marker")


def _run_unified_pre_tool(
    payload: dict,
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke ``unified_pre_tool.py`` as a subprocess with the given payload.

    Args:
        payload: dict written to the hook's stdin as JSON.
        cwd: Working directory for the subprocess.
        env_overrides: Optional env var additions/overrides.

    Returns:
        Completed subprocess result with stdout/stderr captured.
    """
    env = os.environ.copy()
    # Strip any pre-existing bypass to avoid leakage from the caller env.
    env.pop(hook_bypass.ENV_VAR_NAME, None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(UNIFIED_PRE_TOOL)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(cwd),
        env=env,
        timeout=30,
    )


def _decision_from_stdout(stdout: bytes) -> tuple[str, str]:
    """Parse unified_pre_tool stdout JSON and return ``(decision, reason)``.

    Falls back to ``("", "")`` if no JSON is found (treat as 'allow' default).
    """
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return ("", "")
    last_obj: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last_obj = json.loads(line)
        except json.JSONDecodeError:
            continue
    if not last_obj:
        return ("", "")
    spec = last_obj.get("hookSpecificOutput", {})
    decision = spec.get("permissionDecision", last_obj.get("decision", ""))
    reason = spec.get("permissionDecisionReason", last_obj.get("reason", ""))
    return (decision, reason)


# ---------------------------------------------------------------------------
# Deny cases — hard-floor protection survives the universal bypass
# ---------------------------------------------------------------------------


class TestBypassDeniesProtectedInfra:
    """Under bypass, protected-infra Write/Edit is DENIED (Issue #1435)."""

    def test_env_bypass_denies_protected_agent_write(self, project_dir):
        """AUTONOMOUS_DEV_BYPASS=1 + Write to agents/*.md is DENIED."""
        _mark_autonomous_dev_repo(project_dir)
        target = (
            project_dir / "plugins" / "autonomous-dev" / "agents" / "x.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    def test_env_bypass_denies_protected_hook_edit(self, project_dir):
        """AUTONOMOUS_DEV_BYPASS=1 + Edit to hooks/*.py is DENIED."""
        _mark_autonomous_dev_repo(project_dir)
        target = (
            project_dir / "plugins" / "autonomous-dev" / "hooks" / "x.py"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# existing\n")
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "# existing",
                "new_string": "# tampered",
            },
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    def test_env_bypass_denies_protected_lib_write(self, project_dir):
        """AUTONOMOUS_DEV_BYPASS=1 + Write to lib/*.py is DENIED."""
        _mark_autonomous_dev_repo(project_dir)
        target = project_dir / "plugins" / "autonomous-dev" / "lib" / "x.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x = 1\n"},
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    def test_flag_file_bypass_denies_protected_command_write(self, project_dir):
        """.claude/.bypass + Write to commands/*.md is DENIED."""
        _mark_autonomous_dev_repo(project_dir)
        (project_dir / ".claude" / ".bypass").touch()
        target = (
            project_dir / "plugins" / "autonomous-dev" / "commands" / "x.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }
        result = _run_unified_pre_tool(payload, cwd=project_dir)
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    def test_flag_file_bypass_denies_protected_skill_write(self, project_dir):
        """.claude/.bypass + Write to skills/*/SKILL.md is DENIED."""
        _mark_autonomous_dev_repo(project_dir)
        (project_dir / ".claude" / ".bypass").touch()
        target = (
            project_dir
            / "plugins"
            / "autonomous-dev"
            / "skills"
            / "y"
            / "SKILL.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }
        result = _run_unified_pre_tool(payload, cwd=project_dir)
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )

    def test_deny_reason_directs_to_implement(self, project_dir):
        """The protected-infra deny under bypass directs the user to /implement."""
        _mark_autonomous_dev_repo(project_dir)
        (project_dir / ".claude" / ".bypass").touch()
        target = (
            project_dir / "plugins" / "autonomous-dev" / "hooks" / "x.py"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x = 1\n"},
        }
        result = _run_unified_pre_tool(payload, cwd=project_dir)
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "deny", (
            f"expected deny, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}"
        )
        assert "/implement" in reason.lower(), (
            f"deny reason should direct to /implement, got: {reason!r}"
        )


# ---------------------------------------------------------------------------
# Positive controls — bypass otherwise intact for non-protected operations
# ---------------------------------------------------------------------------


class TestBypassStillWorksForNonProtected:
    """The fix is surgical: bypass still allows non-protected operations."""

    def test_bypass_still_allows_nonprotected_write(self, project_dir):
        """bypass + Write to docs/*.md is still ALLOWED (bypass reason)."""
        _mark_autonomous_dev_repo(project_dir)
        target = project_dir / "docs" / "x.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "hello"},
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "allow", (
            f"expected allow for non-protected write under bypass, got "
            f"{decision!r} reason={reason!r}\nstdout={result.stdout!r}"
        )
        assert "bypass" in reason.lower() or "#969" in reason

    def test_bypass_still_allows_bash_under_bypass(self, project_dir):
        """bypass + a plain Bash command is still ALLOWED (bypass reason)."""
        _mark_autonomous_dev_repo(project_dir)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "allow", (
            f"expected allow for bash under bypass, got {decision!r} "
            f"reason={reason!r}\nstdout={result.stdout!r}"
        )
        assert "bypass" in reason.lower() or "#969" in reason


# ---------------------------------------------------------------------------
# Scope guard — protection only applies inside an autonomous-dev repo
# ---------------------------------------------------------------------------


class TestNonAutonomousDevRepoUnaffected:
    """Repos without the implement.md marker are not autonomous-dev repos, so
    ``_is_protected_infrastructure`` returns False and the bypass allow stands.
    """

    def test_no_marker_repo_bypass_allows_protected_path_shape(self, project_dir):
        """No .claude/commands/implement.md marker => an agents/*.md-shaped path
        is NOT protected infrastructure, so bypass allows the write.
        """
        # Deliberately DO NOT call _mark_autonomous_dev_repo.
        target = (
            project_dir / "plugins" / "autonomous-dev" / "agents" / "x.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }
        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "allow", (
            f"expected allow for protected-shaped path in non-autonomous-dev "
            f"repo, got {decision!r} reason={reason!r}\nstdout={result.stdout!r}"
        )
        assert "bypass" in reason.lower() or "#969" in reason
