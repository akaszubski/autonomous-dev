"""Regression tests for universal hook bypass (Issue #969 / #942-A).

Acceptance suite for the universal hook bypass mechanism. Maps 1:1 to the 8
acceptance criteria and 5 test scenarios spelled out in issue #969.

Test classes:

- ``TestIsBypassed`` — AC #1: env var truthy/falsy, file in cwd/ancestor.
- ``TestLogBypassUsed`` — AC #6: telemetry JSONL + stderr fallback, never raises.
- ``TestEnvVarBypassEndToEnd`` — Scenario 1 + AC #2/#3: env var fall-through.
- ``TestFileFlagBypassEndToEnd`` — Scenario 2 + AC #4: flag file fall-through.
- ``TestBypassWalkDiscovery`` — Scenario 3: ancestor-directory walk honored.
- ``TestBypassTelemetry`` — Scenario 4: JSONL line written with required keys.
- ``TestBypassOffDefaultNoRegression`` — Scenario 5 + AC #7: bypass off => normal.

End-to-end tests invoke ``unified_pre_tool.py`` as a subprocess with controlled
stdin and env so the integration is exercised in the same way Claude Code calls
the hook.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup - import the bypass library and unified hook from the repo
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"
LIB_DIR = PLUGIN_ROOT / "lib"
HOOK_DIR = PLUGIN_ROOT / "hooks"
UNIFIED_PRE_TOOL = HOOK_DIR / "unified_pre_tool.py"

for path in (str(LIB_DIR), str(HOOK_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import hook_bypass  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bypass_env(monkeypatch):
    """Ensure the bypass env var is unset for every test by default."""
    monkeypatch.delenv(hook_bypass.ENV_VAR_NAME, raising=False)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create an isolated project root with .claude/ subdir."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _run_unified_pre_tool(
    payload: dict,
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke unified_pre_tool.py as a subprocess with the given JSON payload.

    Args:
        payload: dict written to the hook's stdin as JSON.
        cwd: Working directory for the subprocess.
        env_overrides: Optional env var additions/overrides.

    Returns:
        Completed subprocess result with stdout/stderr captured.
    """
    env = os.environ.copy()
    # Strip any pre-existing bypass to avoid leakage from caller env.
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
    """Parse the unified_pre_tool stdout JSON and return (decision, reason).

    Falls back to ("", "") if no JSON is found (treat as 'allow' default).
    """
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return ("", "")
    # Hook may emit multiple JSON blobs — take the LAST line that parses.
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
# AC #1 — is_bypassed()
# ---------------------------------------------------------------------------


class TestIsBypassed:
    """Coverage for :func:`hook_bypass.is_bypassed` (acceptance criterion #1)."""

    def test_default_off_no_env_no_file(self, project_dir, monkeypatch):
        """No env var + no flag file => False (default)."""
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is False

    def test_env_var_truthy_value_one(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, "1")
        assert hook_bypass.is_bypassed() is True

    @pytest.mark.parametrize("value", ["true", "TRUE", "yes", "YES", "on"])
    def test_env_var_other_truthy_values(self, project_dir, monkeypatch, value):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, value)
        assert hook_bypass.is_bypassed() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", ""])
    def test_env_var_falsy_values_do_not_trigger(
        self, project_dir, monkeypatch, value
    ):
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv(hook_bypass.ENV_VAR_NAME, value)
        assert hook_bypass.is_bypassed() is False

    def test_flag_file_in_cwd(self, project_dir, monkeypatch):
        (project_dir / ".claude" / ".bypass").touch()
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is True

    def test_flag_file_in_ancestor(self, project_dir, monkeypatch):
        nested = project_dir / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        (project_dir / ".claude" / ".bypass").touch()
        monkeypatch.chdir(nested)
        assert hook_bypass.is_bypassed() is True

    def test_flag_file_removed_restores_default(self, project_dir, monkeypatch):
        flag = project_dir / ".claude" / ".bypass"
        flag.touch()
        monkeypatch.chdir(project_dir)
        assert hook_bypass.is_bypassed() is True
        flag.unlink()
        assert hook_bypass.is_bypassed() is False

    def test_explicit_start_dir_overrides_cwd(self, tmp_path, monkeypatch):
        """Passing start_dir takes precedence over current working directory.

        Build two sibling chains so neither directory's walk reaches the
        other's flag file. ``alpha`` has the bypass flag; ``beta`` does not.
        """
        # Use isolated chains rooted at separate ancestors. We give each its
        # own grandparent so the walks don't share ancestors.
        chain_a = tmp_path / "alpha_root" / "alpha"
        chain_b = tmp_path / "beta_root" / "beta"
        chain_a.mkdir(parents=True)
        chain_b.mkdir(parents=True)
        # Put the flag inside chain_a only.
        (chain_a / ".claude").mkdir(parents=True)
        (chain_a / ".claude" / ".bypass").touch()

        # Walking from chain_a (and ancestors up to alpha_root) sees the flag.
        # Walking from chain_b only sees beta_root, tmp_path, /tmp/... — none
        # of which contain a flag because the flag lives under alpha_root.
        # NOTE: walking from chain_b WILL reach tmp_path eventually; ensure
        # tmp_path doesn't have a flag (it doesn't — fixture only creates it
        # in chain_a).
        monkeypatch.chdir(tmp_path)
        assert hook_bypass.is_bypassed(start_dir=chain_a) is True
        assert hook_bypass.is_bypassed(start_dir=chain_b) is False


# ---------------------------------------------------------------------------
# AC #6 — log_bypass_used()
# ---------------------------------------------------------------------------


class TestLogBypassUsed:
    """Coverage for :func:`hook_bypass.log_bypass_used` (acceptance criterion #6)."""

    def test_writes_jsonl_line_with_required_keys(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        hook_bypass.log_bypass_used(
            hook_name="plan_gate.py",
            tool_name="Write",
            reason="env_or_file",
        )
        log_file = project_dir / "_log_target_" / "ignored"  # ensure not used
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists()
        event_lines = [
            json.loads(l)
            for l in log_path.read_text(encoding="utf-8").splitlines()
            if l.strip() and '"marker"' not in l
        ]
        assert len(event_lines) == 1
        event = event_lines[0]
        for key in ("timestamp", "hook_name", "tool_name", "reason"):
            assert key in event, f"missing key: {key}"
        assert event["hook_name"] == "plan_gate.py"
        assert event["tool_name"] == "Write"
        assert event["reason"] == "env_or_file"
        # ISO-8601 timestamp ends with offset (+00:00 for UTC).
        assert "T" in event["timestamp"]

    def test_appends_multiple_calls(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        for i in range(3):
            hook_bypass.log_bypass_used(
                hook_name=f"hook_{i}.py", tool_name="Bash", reason="env_or_file"
            )
        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        event_lines = [
            l
            for l in log_path.read_text(encoding="utf-8").splitlines()
            if l.strip() and '"marker"' not in l
        ]
        assert len(event_lines) == 3
        for i, line in enumerate(event_lines):
            event = json.loads(line)
            assert event["hook_name"] == f"hook_{i}.py"

    def test_stderr_fallback_when_log_dir_unwritable(
        self, project_dir, monkeypatch, capsys
    ):
        """When the log directory cannot be created, fall back to stderr."""
        # Create .claude/logs as a regular FILE so mkdir(parents=True) on the
        # parent works but we can't create the subdir as a directory.
        logs_path = project_dir / ".claude" / "logs"
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        # Replace the path with a file (not a directory).
        logs_path.write_text("not a dir")

        monkeypatch.chdir(project_dir)
        # Must NOT raise.
        hook_bypass.log_bypass_used(hook_name="x.py", tool_name="T", reason="r")
        captured = capsys.readouterr()
        # stderr fallback should mention the bypass tag.
        assert "[hook-bypass]" in captured.err

    def test_never_raises_on_io_error(self, project_dir, monkeypatch):
        """Even with a hostile environment, log_bypass_used must not raise."""

        class _ExplodingPath:
            def __truediv__(self, other):
                raise OSError("simulated FS failure")

        # Patch _resolve_log_path to return something that explodes when used.
        def _bad_resolve(_start=None):
            raise OSError("simulated resolve failure")

        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(hook_bypass, "_resolve_log_path", _bad_resolve)
        # Should not raise.
        hook_bypass.log_bypass_used(hook_name="x.py", tool_name="T", reason="r")


# ---------------------------------------------------------------------------
# Scenario 1 + AC #2/#3 — env var bypass falls through unified_pre_tool
# ---------------------------------------------------------------------------


class TestEnvVarBypassEndToEnd:
    """Env var bypass causes unified_pre_tool to fall through to allow."""

    def test_env_var_makes_blocked_write_fall_through(self, project_dir):
        """Writing to plugins/autonomous-dev/agents/x.md is normally blocked
        outside the pipeline; with the bypass, it falls through to allow.
        """
        # Construct a path that would normally be blocked: an agent file edit.
        # The hook checks file_path against protected infrastructure.
        agents_dir = project_dir / "plugins" / "autonomous-dev" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target = agents_dir / "evil.md"
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }

        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )

        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        decision, reason = _decision_from_stdout(result.stdout)
        # With bypass, decision should be allow (not deny/block).
        assert decision == "allow", (
            f"expected allow under bypass, got {decision!r} (reason={reason!r})\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        # Reason should reference the bypass.
        assert "bypass" in reason.lower() or "#969" in reason


# ---------------------------------------------------------------------------
# Scenario 2 + AC #4 — file flag bypass falls through, removal restores
# ---------------------------------------------------------------------------


class TestFileFlagBypassEndToEnd:
    """``.claude/.bypass`` causes the same fall-through as the env var."""

    def test_flag_file_makes_blocked_write_fall_through(self, project_dir):
        flag = project_dir / ".claude" / ".bypass"
        flag.touch()

        agents_dir = project_dir / "plugins" / "autonomous-dev" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target = agents_dir / "evil.md"
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }

        result = _run_unified_pre_tool(payload, cwd=project_dir)
        decision, reason = _decision_from_stdout(result.stdout)
        assert decision == "allow", (
            f"expected allow with flag file, got {decision!r} reason={reason!r}\n"
            f"stdout={result.stdout!r}"
        )

    def test_removing_flag_file_restores_normal_behavior(self, project_dir):
        """After removing the flag, the hook should behave normally again."""
        flag = project_dir / ".claude" / ".bypass"
        flag.touch()
        flag.unlink()

        # Without bypass, the hook should run normally — invoke a Read which
        # is a native tool and should be allowed without bypass.
        payload = {"tool_name": "Read", "tool_input": {"file_path": str(project_dir)}}
        result = _run_unified_pre_tool(payload, cwd=project_dir)
        decision, reason = _decision_from_stdout(result.stdout)
        # Decision should NOT be the bypass-allow message.
        if decision == "allow":
            assert "#969" not in reason, "bypass reason leaked when flag removed"


# ---------------------------------------------------------------------------
# Scenario 3 — bypass walk finds ancestor flag
# ---------------------------------------------------------------------------


class TestBypassWalkDiscovery:
    """An ancestor's ``.claude/.bypass`` is honored from a deeply nested cwd."""

    def test_ancestor_three_levels_up(self, project_dir):
        nested = project_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (project_dir / ".claude" / ".bypass").touch()
        agents_dir = project_dir / "plugins" / "autonomous-dev" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target = agents_dir / "evil.md"
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }

        result = _run_unified_pre_tool(payload, cwd=nested)
        decision, _ = _decision_from_stdout(result.stdout)
        assert decision == "allow", f"ancestor walk failed; stdout={result.stdout!r}"

    def test_walk_depth_limit_respected(self, project_dir, monkeypatch):
        """Walk terminates within WALK_DEPTH_LIMIT steps."""
        # Confirm the constant exists and is reasonable.
        assert hook_bypass.WALK_DEPTH_LIMIT >= 1
        # Walk from a nested directory with NO flag anywhere up the chain.
        nested = project_dir / "x" / "y" / "z"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        # No flag file => False, but call must complete (no infinite loop).
        assert hook_bypass.is_bypassed() is False


# ---------------------------------------------------------------------------
# Scenario 4 — telemetry recorded
# ---------------------------------------------------------------------------


class TestBypassTelemetry:
    """Every bypass-allowed call writes a JSONL line with required keys."""

    def test_subprocess_bypass_writes_telemetry(self, project_dir):
        agents_dir = project_dir / "plugins" / "autonomous-dev" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target = agents_dir / "evil.md"
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": "x"},
        }

        result = _run_unified_pre_tool(
            payload,
            cwd=project_dir,
            env_overrides={hook_bypass.ENV_VAR_NAME: "1"},
        )
        assert result.returncode == 0

        log_path = project_dir / hook_bypass.LOG_FILE_RELATIVE
        assert log_path.exists(), (
            f"expected telemetry at {log_path}; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        lines = [l for l in log_path.read_text("utf-8").splitlines() if l.strip()]
        assert lines, "telemetry file is empty"
        event_lines = [l for l in lines if '"marker"' not in l]
        assert event_lines, "no per-event telemetry line found (only markers)"
        event = json.loads(event_lines[-1])
        for key in ("timestamp", "hook_name", "tool_name", "reason"):
            assert key in event, f"missing key in telemetry: {key}"
        assert event["hook_name"].endswith(".py")


# ---------------------------------------------------------------------------
# Scenario 5 + AC #7 — bypass off default => no behavioral regression
# ---------------------------------------------------------------------------


class TestBypassOffDefaultNoRegression:
    """With neither env var nor flag, hook tests behave normally."""

    def test_module_import_does_not_raise(self):
        """Importing hook_bypass must not perform side effects that fail."""
        # Re-import to confirm it's importable.
        import importlib
        importlib.reload(hook_bypass)

    def test_default_bypass_is_off(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # No env var, no flag file.
        assert hook_bypass.is_bypassed() is False

    def test_constants_are_present(self):
        assert hook_bypass.ENV_VAR_NAME == "AUTONOMOUS_DEV_BYPASS"
        assert hook_bypass.BYPASS_FILE_RELATIVE == Path(".claude") / ".bypass"
        assert (
            hook_bypass.LOG_FILE_RELATIVE
            == Path(".claude") / "logs" / "hook-bypass.jsonl"
        )
        assert hook_bypass.WALK_DEPTH_LIMIT >= 10
