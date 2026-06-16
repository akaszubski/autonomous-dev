"""Regression tests for the drain-pending commit gate in ``unified_pre_tool.py``.

The gate fires when ``.claude/local/drain_pending.json`` is present with a
non-empty ``issues`` list AND a ``git commit`` Bash invocation does not
reference at least one cluster issue via ``Closes #N`` / ``Fixes #N``.

Covers (per drain-queue durability plan, round-2 acceptance criterion #3):

Unit-level (importlib loads the hook helper directly):
* No marker → no enforcement.
* Marker + ``git commit -m "freelance"`` → BLOCK.
* Marker + ``git commit -m "fix Closes #N"`` (N in marker) → ALLOW.
* Marker + ``git commit -F /path/with-ref`` → ALLOW.
* Marker + ``git commit -F /path/without-ref`` → BLOCK.
* Marker + ``git commit -F -`` (stdin) → BLOCK (uninspectable).
* Marker + ``git commit -F <(gen)`` (proc-sub) → BLOCK (uninspectable).
* Marker + ``git commit`` no flags (editor) → BLOCK (uninspectable).
* Marker + heredoc with literal ``Closes #N`` → ALLOW.
* Marker + heredoc with unresolved ``$MSG`` → BLOCK.
* Marker 3h old (under 4h TTL) → STILL enforced.
* Marker 5h old (past TTL) → STILL enforced by gate (TTL is SessionStart cleanup only).

Integration-level (Issue #1064 pattern — real subprocess):
* ``git commit -F <file>`` without ref → returncode != 0, hook block in stderr.
* ``git commit -m "Closes #N"`` → returncode 0.

Issue: drain-queue durability plan.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "plugins" / "autonomous-dev" / "lib"
_HOOK = _REPO / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"

if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_hook_module():
    """Import the unified_pre_tool module via importlib.

    The hook is not a package; importlib lets us call ``main()`` and the
    private helpers directly.
    """
    spec = importlib.util.spec_from_file_location("uptl_drain_test", _HOOK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def hook_mod():
    return _load_hook_module()


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Create a fake repo with ``.claude/local/`` and chdir to it.

    The drain_pending module resolves its path via ``find_project_root()``
    which walks for ``.git`` / ``.claude`` markers. We give it a real
    ``.claude/`` directory so it picks tmp_path as the root.
    """
    repo = tmp_path / "repo"
    (repo / ".claude" / "local").mkdir(parents=True)
    (repo / ".git").mkdir()  # marker for find_project_root
    monkeypatch.chdir(repo)
    return repo


def _write_marker(
    repo: Path,
    *,
    issues: list[int],
    started_at: Optional[str] = None,
    cluster_tag: str = "UNTAGGED",
) -> None:
    """Write a marker file directly (bypassing DrainPendingMarker.write for age control)."""
    data = {
        "issues": issues,
        "cluster_tag": cluster_tag,
        "started_at": started_at
        or datetime.now(timezone.utc).isoformat(),
        "session_id": "test-session",
    }
    path = repo / ".claude" / "local" / "drain_pending.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unit-level: no marker = no enforcement
# ---------------------------------------------------------------------------


def test_no_marker_no_enforcement(hook_mod, fake_repo: Path) -> None:
    """Without a marker file, the gate is silent for any commit form."""
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "feat: random"'}
    )
    assert result is None


def test_non_git_commit_bash_no_enforcement(hook_mod, fake_repo: Path) -> None:
    """Marker present but command is not git commit → no enforcement."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": "ls -la"}
    )
    assert result is None


def test_empty_command_no_enforcement(hook_mod, fake_repo: Path) -> None:
    """Empty command → no enforcement (not a git commit invocation)."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate({"command": ""})
    assert result is None


# ---------------------------------------------------------------------------
# Unit-level: marker present, various -m forms
# ---------------------------------------------------------------------------


def test_marker_blocks_freelance_commit(hook_mod, fake_repo: Path) -> None:
    """Marker + freelance -m → BLOCK with explicit reason."""
    _write_marker(fake_repo, issues=[1160, 1161])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "fix(hook): freelancing"'}
    )
    assert result is not None
    decision, reason = result
    assert decision == "deny"
    assert "drain marker active" in reason
    assert "1160" in reason


def test_marker_allows_closes_ref(hook_mod, fake_repo: Path) -> None:
    """Marker + Closes #N (N in marker) → ALLOW."""
    _write_marker(fake_repo, issues=[1160, 1161])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "fix: thing\n\nCloses #1160"'}
    )
    assert result is None


def test_marker_allows_fixes_ref(hook_mod, fake_repo: Path) -> None:
    """``Fixes #N`` is also a GitHub-recognized keyword — must be honored."""
    _write_marker(fake_repo, issues=[42])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "Fixes #42 the bug"'}
    )
    assert result is None


def test_marker_blocks_unrelated_closes_ref(hook_mod, fake_repo: Path) -> None:
    """Closes #99999 (not in marker) → BLOCK."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "feat: random\n\nCloses #99999"'}
    )
    assert result is not None
    decision, reason = result
    assert decision == "deny"
    assert "99999" in reason  # got refs reported


def test_marker_allows_one_of_many_refs(hook_mod, fake_repo: Path) -> None:
    """Multiple Closes refs, one matches → ALLOW."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {
            "command": 'git commit -m "fix\n\nCloses #99999\nCloses #1160"'
        }
    )
    assert result is None


def test_marker_message_attached_form(hook_mod, fake_repo: Path) -> None:
    """``--message=msg`` attached form → parsed correctly."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit --message="fix Closes #1160"'}
    )
    assert result is None


def test_marker_case_insensitive_closes(hook_mod, fake_repo: Path) -> None:
    """``closes #1160`` lowercase → still recognized."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "fix\n\ncloses #1160"'}
    )
    assert result is None


# ---------------------------------------------------------------------------
# Unit-level: -F file-based forms
# ---------------------------------------------------------------------------


def test_marker_allows_file_with_ref(
    hook_mod, fake_repo: Path, tmp_path: Path
) -> None:
    """``-F /path`` with file containing Closes #N → ALLOW."""
    _write_marker(fake_repo, issues=[1160])
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text("fix the thing\n\nCloses #1160\n", encoding="utf-8")
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": f"git commit -F {msg_file}"}
    )
    assert result is None


def test_marker_blocks_file_without_ref(
    hook_mod, fake_repo: Path, tmp_path: Path
) -> None:
    """``-F /path`` with file lacking Closes ref → BLOCK."""
    _write_marker(fake_repo, issues=[1160])
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text("just a random message\n", encoding="utf-8")
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": f"git commit -F {msg_file}"}
    )
    assert result is not None
    assert result[0] == "deny"


def test_marker_blocks_file_with_shell_expansion(
    hook_mod, fake_repo: Path, tmp_path: Path
) -> None:
    """``-F /path`` with file containing ``$VAR`` → BLOCK (unresolved expansion)."""
    _write_marker(fake_repo, issues=[1160])
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text("fix Closes #1160 with $UNRESOLVED\n", encoding="utf-8")
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": f"git commit -F {msg_file}"}
    )
    assert result is not None
    assert result[0] == "deny"
    assert "uninspectable" in result[1].lower()


def test_marker_blocks_file_missing(
    hook_mod, fake_repo: Path
) -> None:
    """``-F /does/not/exist`` → BLOCK (uninspectable)."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": "git commit -F /this/path/does/not/exist/msg.txt"}
    )
    assert result is not None
    assert result[0] == "deny"


# ---------------------------------------------------------------------------
# Unit-level: uninspectable payload sources
# ---------------------------------------------------------------------------


def test_marker_blocks_stdin(hook_mod, fake_repo: Path) -> None:
    """``-F -`` (stdin) → BLOCK with explicit reason."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": "git commit -F -"}
    )
    assert result is not None
    assert result[0] == "deny"
    assert "uninspectable" in result[1].lower()


def test_marker_blocks_process_substitution(hook_mod, fake_repo: Path) -> None:
    """``-F <(generate)`` → BLOCK (pseudo-device)."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": "git commit -F <(echo Closes #1160)"}
    )
    assert result is not None
    assert result[0] == "deny"


def test_marker_blocks_no_flags_editor_mode(hook_mod, fake_repo: Path) -> None:
    """``git commit`` with no -m/-F → BLOCK (would open $EDITOR)."""
    _write_marker(fake_repo, issues=[1160])
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": "git commit"}
    )
    assert result is not None
    assert result[0] == "deny"


# ---------------------------------------------------------------------------
# Unit-level: heredoc forms
# ---------------------------------------------------------------------------


def test_marker_allows_heredoc_with_literal_closes(
    hook_mod, fake_repo: Path
) -> None:
    """Heredoc body containing literal ``Closes #N`` → ALLOW."""
    _write_marker(fake_repo, issues=[1160])
    command = (
        "git commit -m \"$(cat <<'EOF'\n"
        "fix: the thing\n\n"
        "Closes #1160\n"
        "EOF\n"
        ")\""
    )
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": command}
    )
    assert result is None


def test_marker_blocks_heredoc_with_unresolved_var(
    hook_mod, fake_repo: Path
) -> None:
    """Heredoc body with unresolved ``$MSG`` → BLOCK."""
    _write_marker(fake_repo, issues=[1160])
    command = (
        "git commit -m \"$(cat <<EOF\n"
        "fix: $MSG\n\n"
        "Closes #1160\n"
        "EOF\n"
        ")\""
    )
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": command}
    )
    assert result is not None
    assert result[0] == "deny"
    assert "uninspectable" in result[1].lower()


def test_marker_blocks_heredoc_with_backtick(hook_mod, fake_repo: Path) -> None:
    """Heredoc body containing backticks → BLOCK."""
    _write_marker(fake_repo, issues=[1160])
    command = (
        "git commit -m \"$(cat <<EOF\n"
        "fix: `whoami`\n\n"
        "Closes #1160\n"
        "EOF\n"
        ")\""
    )
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": command}
    )
    assert result is not None
    assert result[0] == "deny"


# ---------------------------------------------------------------------------
# Unit-level: TTL behavior — gate NEVER consults TTL
# ---------------------------------------------------------------------------


def test_marker_3h_old_still_enforced(hook_mod, fake_repo: Path) -> None:
    """Marker 3h old (under 4h STALE_MINUTES) — gate still fires.

    Verifies the gate does not pretend to consult TTL.
    """
    started = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    _write_marker(fake_repo, issues=[1160], started_at=started)
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "freelance"'}
    )
    assert result is not None
    assert result[0] == "deny"


def test_marker_5h_old_still_enforced_by_gate(
    hook_mod, fake_repo: Path
) -> None:
    """Marker 5h old (PAST STALE_MINUTES) — gate STILL fires.

    TTL is for SessionStart cleanup ONLY. The hook NEVER consults TTL,
    so a stale marker still blocks. This is the canonical regression
    against round-2 concern (c): "TTL semantics — long /implement runs
    of 2h+ MUST remain covered."
    """
    started = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    _write_marker(fake_repo, issues=[1160], started_at=started)
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "freelance"'}
    )
    assert result is not None
    assert result[0] == "deny"


# ---------------------------------------------------------------------------
# Unit-level: marker corruption tolerance
# ---------------------------------------------------------------------------


def test_marker_malformed_json_no_enforcement(
    hook_mod, fake_repo: Path
) -> None:
    """Corrupt marker JSON → read() returns None → no enforcement."""
    path = fake_repo / ".claude" / "local" / "drain_pending.json"
    path.write_text("{not valid json", encoding="utf-8")
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "anything"'}
    )
    assert result is None


def test_marker_empty_issues_no_enforcement(
    hook_mod, fake_repo: Path
) -> None:
    """Marker with empty issues list → no enforcement."""
    _write_marker(fake_repo, issues=[])
    # Manually write since DrainPendingMarker.write rejects empty issues.
    result = hook_mod._check_drain_pending_commit_gate(
        {"command": 'git commit -m "anything"'}
    )
    assert result is None


# ---------------------------------------------------------------------------
# Integration-level (Issue #1064 pattern) — real subprocess + real hook
# ---------------------------------------------------------------------------


def _build_hook_env(repo: Path) -> dict:
    """Build environment for invoking the hook subprocess.

    Sets CWD-equivalent state so drain_pending can find the marker.
    """
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _invoke_hook(
    command: str, *, cwd: Path, env: Optional[dict] = None
) -> subprocess.CompletedProcess:
    """Invoke unified_pre_tool.py as a real subprocess with PreToolUse stdin.

    Returns the CompletedProcess; the hook always exits 0 — block/allow is
    in stdout JSON ``hookSpecificOutput.permissionDecision``.
    """
    stdin_data = json.dumps(
        {
            "session_id": "integ-drain-gate",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
    )
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env if env is not None else _build_hook_env(cwd),
        timeout=30,
    )


def _decision_from(proc: subprocess.CompletedProcess) -> str:
    """Extract permissionDecision from hook stdout."""
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "ERROR"
    return (
        payload.get("hookSpecificOutput", {}).get("permissionDecision", "ERROR")
    )


def test_integration_hook_blocks_freelance_via_subprocess(
    fake_repo: Path,
) -> None:
    """Real subprocess hook invocation — marker + freelance → deny in stdout."""
    _write_marker(fake_repo, issues=[1160])
    proc = _invoke_hook(
        'git commit -m "feat: freelance"', cwd=fake_repo
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    decision = _decision_from(proc)
    assert decision == "deny", f"unexpected decision: {decision} | stdout: {proc.stdout}"


def test_integration_hook_allows_closes_ref_via_subprocess(
    fake_repo: Path,
) -> None:
    """Real subprocess — marker + Closes #N → allow OR ask (not deny).

    Note: native Bash tool may still proceed to other validation layers
    (e.g., MCP security). The drain gate's specific job is "do not deny on
    this commit."
    """
    _write_marker(fake_repo, issues=[1160])
    proc = _invoke_hook(
        'git commit -m "fix: Closes #1160"', cwd=fake_repo
    )
    assert proc.returncode == 0
    decision = _decision_from(proc)
    assert decision != "deny", (
        f"expected non-deny for commit with Closes #1160; got {decision} | "
        f"stdout: {proc.stdout}"
    )


def test_integration_hook_blocks_F_without_ref_via_subprocess(
    fake_repo: Path, tmp_path: Path
) -> None:
    """Real subprocess — marker + -F file lacking Closes ref → deny."""
    _write_marker(fake_repo, issues=[1160])
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text("random message", encoding="utf-8")
    proc = _invoke_hook(
        f"git commit -F {msg_file}", cwd=fake_repo
    )
    assert proc.returncode == 0
    decision = _decision_from(proc)
    assert decision == "deny"


def test_integration_hook_no_marker_no_enforcement_via_subprocess(
    fake_repo: Path,
) -> None:
    """Real subprocess — no marker → not denied by this gate."""
    proc = _invoke_hook(
        'git commit -m "feat: random freelance"', cwd=fake_repo
    )
    assert proc.returncode == 0
    decision = _decision_from(proc)
    assert decision != "deny", (
        f"unexpected deny without marker: {proc.stdout}"
    )
