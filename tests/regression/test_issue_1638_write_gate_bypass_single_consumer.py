"""Regression: the write-pipeline one-shot bypass must only be spent on a refusal.

Issue #1638. The operator escape hatch ``/tmp/skip_write_pipeline_gate`` is
advertised in the write-pipeline gate's own block message
("Operator one-shot bypass: touch /tmp/skip_write_pipeline_gate"), but it was
consumed EAGERLY at the top of both
``_check_write_pipeline_required`` (Write/Edit path) and
``_check_bash_code_file_pipeline_required`` (Bash path) — before either gate
had established that it applied at all.

Observed failure: ``touch /tmp/skip_write_pipeline_gate``, then confirm the
file exists (a Bash tool call), then Write to a production-code path. The Bash
call's hook invocation ate the token even though ``ls`` writes to nothing, and
the Write was refused with ``Tier: full``. The operator followed the printed
instructions, burned the one-shot, and was blocked anyway.

Two consumption classes are locked here:

1. **Cross-gate steal** — a Bash command that the (advisory-only, Issue #1408)
   Bash gate would never refuse must not consume the token. A test that only
   asserts "marker present permits a Write" would still pass if a second
   consumer were reintroduced on the Bash path, so the intervening-Bash
   sequence is asserted end-to-end through the hook subprocess.
2. **Intra-gate waste** — a Write/Edit the gate allows anyway (docs, tests,
   scratch, out-of-tree) must not consume the token either.

Both arms of the guard are exercised: the token PERMITS a production-code
Write, and its absence REFUSES the same Write.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# tests/regression/test_*.py -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
HOOK_DEPLOYED = REPO_ROOT / ".claude" / "hooks" / "unified_pre_tool.py"

SENTINEL = Path("/tmp/skip_write_pipeline_gate")

# A tracked, non-protected production-code path that genuinely reaches the
# write-pipeline gate (protected infrastructure such as lib/*.py is refused
# earlier by the Issue #1435 hard floor and would never exercise this gate).
GATED_CODE_PATH = str(REPO_ROOT / "scripts" / "audit_inventory.py")

sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
import unified_pre_tool as upt  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_sentinel():
    """Remove the sentinel before AND after each test.

    /tmp is not cleared between pytest invocations, so a sentinel left behind
    by a prior run (or by a prior test in this module) would make a later test
    pass or fail for the wrong reason.
    """
    if SENTINEL.exists():
        SENTINEL.unlink()
    yield
    if SENTINEL.exists():
        SENTINEL.unlink()


# ---------------------------------------------------------------------------
# Subprocess driver — exercises the DEPLOYED hook the way Claude Code does.
# ---------------------------------------------------------------------------


def _run_hook(payload: dict[str, Any], hook_path: Path = HOOK_SOURCE) -> dict[str, Any]:
    """Drive the hook as a subprocess with a PreToolUse payload on stdin.

    The hook signals its verdict through ``hookSpecificOutput.permissionDecision``
    with exit code 0 — it does NOT use exit code 2. Asserting on the exit code
    alone would pass vacuously, so callers assert on the decision and reason.
    """
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(REPO_ROOT)},
        timeout=120,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(
            f"Hook did not emit JSON on stdout (exit={proc.returncode}).\n"
            f"stdout: {proc.stdout[:800]!r}\n"
            f"stderr: {proc.stderr[:800]!r}"
        ) from exc


def _decision(out: dict[str, Any]) -> str:
    hso = out.get("hookSpecificOutput", {})
    return hso.get("permissionDecision", out.get("decision", ""))


def _reason(out: dict[str, Any]) -> str:
    hso = out.get("hookSpecificOutput", {})
    return str(hso.get("permissionDecisionReason", out.get("reason", "")))


def _write_payload(file_path: str) -> dict[str, Any]:
    return {
        "session_id": "test_issue_1638",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "x"},
    }


def _bash_payload(command: str) -> dict[str, Any]:
    return {
        "session_id": "test_issue_1638",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


# ---------------------------------------------------------------------------
# Instrument controls — prove the driver can observe BOTH verdicts before any
# result derived from it is trusted.
# ---------------------------------------------------------------------------


class TestDriverControls:
    """Positive and negative controls for the subprocess driver itself."""

    def test_negative_control_no_sentinel_refuses_production_write(self) -> None:
        """Control: with no sentinel, the gate REFUSES and names its tier.

        Asserting on the reason (not the exit code) confirms the *write-pipeline
        gate* answered, rather than some upstream fast path.
        """
        out = _run_hook(_write_payload(GATED_CODE_PATH))
        assert _decision(out) == "deny", f"expected deny, got {out!r}"
        assert "requires the /implement pipeline" in _reason(out), _reason(out)
        assert "Tier: " in _reason(out), _reason(out)

    def test_positive_control_sentinel_permits_production_write(self) -> None:
        """Control: with the sentinel, the same Write is PERMITTED and the
        sentinel is consumed."""
        SENTINEL.write_text("issue-1638 positive control")
        out = _run_hook(_write_payload(GATED_CODE_PATH))
        assert _decision(out) == "allow", f"expected allow, got {out!r}"
        assert "requires the /implement pipeline" not in _reason(out), _reason(out)
        assert not SENTINEL.exists(), "sentinel must be consumed when it buys a bypass"


# ---------------------------------------------------------------------------
# Class 1 — cross-gate steal (the reported failure)
# ---------------------------------------------------------------------------


class TestBashPathDoesNotStealTheToken:
    """The advisory Bash gate must never consume the Write/Edit gate's token."""

    @pytest.mark.parametrize(
        "command",
        [
            # The exact confirm-step from the bug report.
            "ls -la /tmp/skip_write_pipeline_gate",
            # A command that reaches the Bash gate's *detector* and is rejected
            # as a non-target — a different shape from the reproducer.
            "git status --short",
            # A Bash command that the advisory Bash gate DOES flag (it writes a
            # code file). It emits an advisory, never a refusal, so it still
            # must not spend a token reserved for buying passage past refusals.
            "cat > scripts/scratch_helper_1638.py << 'EOF'\nx = 1\nEOF",
        ],
    )
    def test_intervening_bash_call_does_not_consume_sentinel(self, command: str) -> None:
        """touch -> (any Bash call) -> Write must still be PERMITTED."""
        SENTINEL.write_text("issue-1638 cross-gate")

        bash_out = _run_hook(_bash_payload(command))
        assert SENTINEL.exists(), (
            f"Bash command {command!r} consumed the one-shot write-gate sentinel. "
            f"Bash verdict was {_decision(bash_out)!r} — nothing was refused, so "
            f"nothing should have been bought. This is Issue #1638."
        )

        write_out = _run_hook(_write_payload(GATED_CODE_PATH))
        assert _decision(write_out) == "allow", (
            "Write was refused after an intervening Bash call ate the operator's "
            f"one-shot bypass. Reason: {_reason(write_out)}"
        )
        assert not SENTINEL.exists(), "sentinel must be consumed by the Write it bought"

    def test_bash_gate_function_never_returns_operator_bypass(self) -> None:
        """Unit-level lock: the Bash gate must not have a bypass branch at all.

        Structural guard against a second consumer being reintroduced: even with
        the sentinel present, the Bash gate must classify on its own merits.
        """
        SENTINEL.write_text("issue-1638 unit")
        block, tier, _directive, _target = upt._check_bash_code_file_pipeline_required(
            "ls -la /tmp"
        )
        assert tier != "operator_bypass", (
            "The Bash gate consumed/honoured the write-gate sentinel. It is "
            "advisory-only (Issue #1408) and must not be a second consumer."
        )
        assert block is False
        assert SENTINEL.exists(), "Bash gate must leave the sentinel untouched"


# ---------------------------------------------------------------------------
# Class 2 — intra-gate waste
# ---------------------------------------------------------------------------


class TestNonRefusedWritesDoNotConsumeTheToken:
    """A Write/Edit the gate allows anyway must not spend the one-shot."""

    @pytest.mark.parametrize(
        "relative_path,expected_tier",
        [
            ("README.md", "tier0_non_code"),  # docs — allowed by Tier 0e
            ("tests/unit/test_nothing_1638.py", "tier0_test_file"),  # Tier 0f
        ],
    )
    def test_allowed_write_leaves_sentinel_intact(
        self, relative_path: str, expected_tier: str
    ) -> None:
        SENTINEL.write_text("issue-1638 intra-gate")
        block, tier, _directive = upt._check_write_pipeline_required(
            "Write", str(REPO_ROOT / relative_path), "", "x" * 200
        )
        assert block is False
        assert tier == expected_tier, f"expected {expected_tier}, got {tier}"
        assert SENTINEL.exists(), (
            f"A Write to {relative_path} — which the gate allows unconditionally "
            f"(tier={tier}) — consumed the operator's one-shot bypass. Nothing was "
            f"refused, so nothing should have been bought. This is Issue #1638."
        )

    def test_scratch_path_write_leaves_sentinel_intact(self) -> None:
        """Scratch paths (Tier 0g) are never gated, so they must not consume."""
        SENTINEL.write_text("issue-1638 scratch")
        block, tier, _directive = upt._check_write_pipeline_required(
            "Write", "/private/tmp/claude-501/helper_1638.py", "", "x" * 200
        )
        assert block is False
        assert tier == "tier0_scratch_path", f"got {tier}"
        assert SENTINEL.exists(), (
            "A scratch-path Write consumed the operator's one-shot bypass."
        )


# ---------------------------------------------------------------------------
# One-shot semantics preserved (the FORBIDDEN alternative fix)
# ---------------------------------------------------------------------------


class TestStillOneShot:
    """The repair must not turn a one-shot bypass into a persistent one."""

    def test_second_production_write_is_refused_again(self) -> None:
        SENTINEL.write_text("issue-1638 one-shot")

        first = _run_hook(_write_payload(GATED_CODE_PATH))
        assert _decision(first) == "allow", _reason(first)
        assert not SENTINEL.exists()

        second = _run_hook(_write_payload(GATED_CODE_PATH))
        assert _decision(second) == "deny", (
            "The bypass survived its first use — a one-shot escape hatch was "
            f"converted into a persistent one. Reason: {_reason(second)}"
        )
        assert "requires the /implement pipeline" in _reason(second)


# ---------------------------------------------------------------------------
# Audit logging preserved (Issue #1356 / #1408)
# ---------------------------------------------------------------------------


class TestConsumptionIsLoggedExactlyOnce:
    """Every consumption must still be logged — not zero times, not twice."""

    def test_single_log_entry_per_consumption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime as _dt

        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_scratch_path", lambda _p: False)
        monkeypatch.setattr(upt, "_is_gated_repo_source", lambda _p: True)

        SENTINEL.write_text("issue-1638 audit reason")
        block, tier, _directive = upt._check_write_pipeline_required(
            "Edit", "/home/user/app/service.py", "", "\n".join(f"def f{i}(): pass" for i in range(20))
        )
        assert block is False
        assert tier == "operator_bypass"

        log_file = (
            tmp_path
            / ".claude"
            / "logs"
            / "activity"
            / f"{_dt.datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        assert log_file.exists(), "consumption must be logged (Issue #1356)"
        entries = [
            json.loads(line)
            for line in log_file.read_text().splitlines()
            if line.strip()
        ]
        consumed = [
            e for e in entries if e.get("event") == "write_gate_operator_bypass_consumed"
        ]
        assert len(consumed) == 1, f"expected exactly 1 log entry, got {len(consumed)}"
        # Issue #1408: sentinel body is the scoped-escape reason.
        assert consumed[0]["reason"] == "issue-1638 audit reason"
        assert consumed[0]["file_path"] == "/home/user/app/service.py"
        assert consumed[0]["sentinel_age_seconds"] >= 0, (
            "sentinel age must still be recorded — the log must run BEFORE unlink"
        )

    def test_no_log_entry_when_nothing_consumed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative control for the logging assertion above."""
        import datetime as _dt

        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_gated_repo_source", lambda _p: True)

        # No sentinel on disk.
        block, _tier, _directive = upt._check_write_pipeline_required(
            "Edit", "/home/user/app/service.py", "", "\n".join(f"def f{i}(): pass" for i in range(20))
        )
        assert block is True

        log_file = (
            tmp_path
            / ".claude"
            / "logs"
            / "activity"
            / f"{_dt.datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        entries = (
            [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
            if log_file.exists()
            else []
        )
        assert not [
            e for e in entries if e.get("event") == "write_gate_operator_bypass_consumed"
        ], "logged a consumption that never happened"


# ---------------------------------------------------------------------------
# Single-consumer structural lock
# ---------------------------------------------------------------------------


def test_exactly_one_sentinel_consumption_site_in_the_hook() -> None:
    """Source-level lock: only one place may unlink the sentinel.

    The behavioural arms above cover the two consumption classes observed in
    Issue #1638, but they are shaped around the tool paths that exist today. A
    future third gate that eagerly consumed the sentinel would slip past them.
    Pinning the unlink count to one keeps the invariant — "a single one-shot
    token must not be consumable by more than one gate" — checkable by
    machine rather than by reading.

    Deployment note: ``.claude/hooks/unified_pre_tool.py`` is a byte-identical
    copy produced by ``scripts/deploy-all.sh``, whose deploy-gate refuses to
    ship an uncommitted working tree. This asserts the property of the source
    that gets copied; the deploy-gate is what carries it to the executing copy.
    """
    source = HOOK_SOURCE.read_text()
    # The sentinel is named exactly once as a Path constant, and consumed
    # exactly once, inside _consume_write_gate_bypass.
    assert source.count('Path("/tmp/skip_write_pipeline_gate")') == 1, (
        "The write-gate sentinel path is constructed more than once — each "
        "construction site is a candidate consumer. Use "
        "WRITE_GATE_BYPASS_SENTINEL."
    )
    consume_fn = source.split("def _consume_write_gate_bypass(", 1)
    assert len(consume_fn) == 2, "_consume_write_gate_bypass is missing"
    body = consume_fn[1].split("\ndef ", 1)[0]
    assert "skip_file.unlink()" in body, (
        "_consume_write_gate_bypass must actually consume the sentinel"
    )
    # No other function may unlink it.
    assert source.count("skip_file.unlink()") == 1, (
        "More than one site unlinks the write-gate sentinel — this is the "
        "Issue #1638 defect shape. Route all consumption through "
        "_consume_write_gate_bypass."
    )
