"""Regression: one PreToolUse event spawns N hook processes, not one.

Issue #1641 — the half of Issue #1638 that commit ``f2d841ff`` did not reach.

WHAT WAS ACTUALLY WRONG
-----------------------
``unified_pre_tool.py`` is registered for PreToolUse with matcher ``*`` on TWO
settings surfaces at once — the project ``.claude/settings.json`` and the user's
``~/.claude/settings.json``. Claude Code merges hook registrations across
surfaces and runs every match concurrently, so a single Write launched two
copies of the hook. The write-gate one-shot token is a non-idempotent side
effect performed per PROCESS, so the first copy spent it and allowed, and the
second copy — looking at a ``/tmp`` that no longer had a sentinel in it —
refused. Claude Code takes the deny.

The production activity log carries the receipt (``.claude/logs/activity/``,
2026-09-01)::

    23:00:28.181026  Write allow  write_pipeline_gate: operator_bypass
    23:00:28.185267  Write allow  Native tool 'Write' - hook bypass (...)
    23:00:28.548431  Write deny   BLOCKED: ... Tier: full

Three log lines, 367 ms apart, for ONE tool call. A single hook run takes
~1.7 s, so the third line cannot be a sequential successor of the second — the
two copies overlapped.

This also corrects the standing hypothesis that the reason string "Native tool
'Write' - hook bypass (settings.json governs)" indicated a fast path that
skipped the gate. It does not: that is the fast path's TERMINAL allow, emitted
*after* the write-pipeline gate has already been consulted and passed. The
single-subprocess replay reached the gate; it simply was not duplicated.

WHAT THIS HARNESS PROVES, AND WHAT IT DOES NOT
----------------------------------------------
PROVES: that N concurrent invocations of the hook, driven by one identical
PreToolUse payload — the exact topology two settings surfaces produce — all
return the same verdict, and that exactly one of them spends and logs the
token. Run against the pre-fix hook, the concurrent arm returns
``['allow', 'deny']``; against the fixed hook it returns ``['allow', 'allow']``.

DOES NOT PROVE: how Claude Code aggregates N verdicts into one. The tool call
originates in the Claude Code runtime, not in pytest, so no test process can
assert on the runtime's aggregation. Empirically it takes the deny (that is the
reported symptom), which is why making every copy agree is the fix rather than
hoping the allow wins.

DOES NOT PROVE: that the DEPLOYED copies at ``.claude/hooks/`` and
``~/.claude/hooks/`` carry the fix. They are produced by
``scripts/deploy-all.sh``, whose deploy-gate refuses an uncommitted tree. These
tests assert the property of the source that gets copied.
"""

from __future__ import annotations

import concurrent.futures
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# tests/regression/test_*.py -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"

SENTINEL = Path("/tmp/skip_write_pipeline_gate")
RECEIPT_GLOB = "/tmp/.skip_write_pipeline_gate.receipt.*"

# A tracked, non-protected production-code path that genuinely reaches the
# write-pipeline gate. Protected infrastructure (lib/*.py, hooks/*.py) is
# refused earlier by the Issue #1435 hard floor and never exercises this gate.
GATED_CODE_PATH = str(REPO_ROOT / "scripts" / "audit_inventory.py")
# A second gated path of a DIFFERENT shape, so the guard is not scoped to the
# one file that happened to reproduce the bug.
GATED_CODE_PATH_ALT = str(REPO_ROOT / "scripts" / "derive_signals.py")
UNGATED_DOC_PATH = str(REPO_ROOT / "README.md")

sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
import unified_pre_tool as upt  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_sentinel_and_receipts():
    """Clear the sentinel AND every consumption receipt, before and after.

    /tmp is not cleared between pytest invocations. A receipt left by a prior
    run is exactly the kind of stale shared state that makes a second
    consecutive run of this module pass or fail for the wrong reason.
    """

    def _purge() -> None:
        if SENTINEL.exists():
            SENTINEL.unlink()
        for stale in glob.glob(RECEIPT_GLOB):
            try:
                os.unlink(stale)
            except OSError:
                pass

    _purge()
    yield
    _purge()


# ---------------------------------------------------------------------------
# Subprocess driver — one process per invocation, as Claude Code does it.
# ---------------------------------------------------------------------------


def _run_hook(payload: dict[str, Any]) -> tuple[str, str]:
    """Drive the hook as a subprocess and return (decision, reason).

    The hook signals its verdict through ``hookSpecificOutput.permissionDecision``
    with exit code 0 in EVERY case, including denials. Asserting on the exit code
    would pass vacuously, so every assertion here is on the decision and reason.
    """
    proc = subprocess.run(
        [sys.executable, str(HOOK_SOURCE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(REPO_ROOT)},
        timeout=180,
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(
            f"Hook did not emit JSON on stdout (exit={proc.returncode}).\n"
            f"stdout: {proc.stdout[:800]!r}\nstderr: {proc.stderr[:800]!r}"
        ) from exc
    hso = out.get("hookSpecificOutput", {})
    return (
        str(hso.get("permissionDecision", out.get("decision", ""))),
        str(hso.get("permissionDecisionReason", out.get("reason", ""))),
    )


def _run_hook_fanout(payload: dict[str, Any], copies: int) -> list[tuple[str, str]]:
    """Launch ``copies`` hook processes CONCURRENTLY for one identical payload.

    This is the production topology: N settings surfaces matching one tool call
    means N processes started together, each reading the same ``/tmp``.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=copies) as pool:
        return list(pool.map(lambda _i: _run_hook(payload), range(copies)))


def _write_payload(file_path: str, content: str = "x") -> dict[str, Any]:
    return {
        "session_id": "test_issue_1641",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }


def _edit_payload(file_path: str, new_string: str = "y") -> dict[str, Any]:
    return {
        "session_id": "test_issue_1641",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "",
            "new_string": "\n".join(f"def f{i}(): pass" for i in range(30)) + new_string,
        },
    }


def _bash_payload(command: str) -> dict[str, Any]:
    return {
        "session_id": "test_issue_1641",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def _activity_log() -> Path:
    """Today's activity log — resolved per call so a date rollover cannot skew it."""
    return (
        REPO_ROOT / ".claude" / "logs" / "activity" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    )


def _activity_log_line_count() -> int:
    log_file = _activity_log()
    return len(log_file.read_text().splitlines()) if log_file.exists() else 0


def _consumption_records_since(before: int) -> list[dict[str, Any]]:
    """Every ``write_gate_operator_bypass_consumed`` record written after ``before``."""
    log_file = _activity_log()
    if not log_file.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_file.read_text().splitlines()[before:]:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("event") == "write_gate_operator_bypass_consumed":
            records.append(entry)
    return records


def registered_pretooluse_copies() -> int:
    """Count PreToolUse registrations of this hook across readable surfaces.

    Advisory only — the user's global settings live outside the repo, so this
    is reported in failure messages to explain the fan-out size rather than
    asserted on.
    """
    count = 0
    for settings_path in (
        REPO_ROOT / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.json",
    ):
        try:
            data = json.loads(settings_path.read_text())
        except (OSError, ValueError):
            continue
        for matcher in data.get("hooks", {}).get("PreToolUse", []) or []:
            for entry in matcher.get("hooks", []) or []:
                if "unified_pre_tool.py" in str(entry.get("command", "")):
                    count += 1
    return count


# ---------------------------------------------------------------------------
# Instrument controls — the harness must be able to observe BOTH verdicts,
# in BOTH the single and the concurrent driving mode, before any result
# derived from it means anything.
# ---------------------------------------------------------------------------


class TestHarnessControls:
    """Positive and negative controls for the concurrent subprocess driver."""

    def test_negative_control_single_invocation_no_sentinel_refuses(self) -> None:
        decision, reason = _run_hook(_write_payload(GATED_CODE_PATH))
        assert decision == "deny", f"expected deny, got {decision!r}: {reason}"
        assert "requires the /implement pipeline" in reason, reason
        assert "Tier: " in reason, reason

    def test_positive_control_single_invocation_with_sentinel_permits(self) -> None:
        SENTINEL.write_text("issue-1641 positive control")
        decision, reason = _run_hook(_write_payload(GATED_CODE_PATH))
        assert decision == "allow", f"expected allow, got {decision!r}: {reason}"
        assert not SENTINEL.exists(), "sentinel must be consumed when it buys a bypass"

    def test_negative_control_fanout_without_sentinel_refuses_every_copy(self) -> None:
        """The concurrent driver can observe a REFUSAL, not only an allow.

        Without this arm, an all-allow result from the fan-out below would be
        indistinguishable from a driver that cannot produce a deny at all.
        """
        results = _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=3)
        assert [d for d, _r in results] == ["deny"] * 3, results
        for _decision, reason in results:
            assert "requires the /implement pipeline" in reason, reason

    def test_receipts_are_not_created_when_nothing_is_consumed(self) -> None:
        """Negative control for the receipt mechanism itself."""
        _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=2)
        assert not glob.glob(RECEIPT_GLOB), (
            "a consumption receipt was written for a call that consumed nothing"
        )


# ---------------------------------------------------------------------------
# The reported failure — reproduced as a concurrent fan-out.
# ---------------------------------------------------------------------------


class TestConcurrentFanoutAgreesOnTheVerdict:
    """Every copy spawned for one PreToolUse event must return the same verdict."""

    @pytest.mark.parametrize("copies", [2, 3, 4])
    def test_all_copies_permit_the_write_when_the_sentinel_is_present(
        self, copies: int
    ) -> None:
        SENTINEL.write_text("issue-1641 fan-out")
        results = _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=copies)
        decisions = [d for d, _r in results]
        registered = registered_pretooluse_copies()
        assert decisions == ["allow"] * copies, (
            f"{decisions.count('deny')} of {copies} concurrent copies of the hook "
            f"refused a Write the operator had already paid for. This is Issue "
            f"#1641: the one-shot token was spent by whichever copy got there "
            f"first, and the rest saw an empty /tmp. "
            f"({registered} PreToolUse registrations of this hook are visible from "
            f"here; Claude Code runs them all.) Reasons: "
            + " || ".join(r[:120] for _d, r in results)
        )
        for _decision, reason in results:
            assert "requires the /implement pipeline" not in reason, reason
        assert not SENTINEL.exists(), "the token must still be spent exactly once"

    def test_edit_tool_fanout_also_agrees(self) -> None:
        """Different tool, different file — the guard covers the class.

        The reproducer was a ``Write`` to ``mechanism_view.py``. If the repair
        only held for that shape it would be scoped to the instance.
        """
        SENTINEL.write_text("issue-1641 edit shape")
        results = _run_hook_fanout(_edit_payload(GATED_CODE_PATH_ALT), copies=3)
        assert [d for d, _r in results] == ["allow"] * 3, results
        assert not SENTINEL.exists()

    def test_a_second_fanout_after_a_stale_receipt_still_agrees(self) -> None:
        """A leftover receipt must not degrade the NEXT fan-out back to the bug.

        The first fan-out leaves a receipt keyed to this payload. When the
        operator re-arms the sentinel and repeats the same write, the stale
        receipt must be swept and a fresh claim made — otherwise the second
        fan-out has no coordination and one copy refuses again.
        """
        SENTINEL.write_text("issue-1641 first fan-out")
        assert [d for d, _r in _run_hook_fanout(_write_payload(GATED_CODE_PATH), 2)] == [
            "allow"
        ] * 2
        assert glob.glob(RECEIPT_GLOB), "precondition: a stale receipt is left behind"

        SENTINEL.write_text("issue-1641 second fan-out")
        results = _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=2)
        assert [d for d, _r in results] == ["allow"] * 2, (
            "the second fan-out fell back to per-process consumption because a "
            "stale receipt blocked the claim: " + " || ".join(r[:120] for _d, r in results)
        )
        assert not SENTINEL.exists()

    def test_a_reclaimed_stale_receipt_still_logs_exactly_one_consumption(self) -> None:
        """Stale receipt AND live siblings racing — the untested combination.

        ``test_a_second_fanout_after_a_stale_receipt_still_agrees`` proves the
        verdicts agree; ``test_consumption_is_logged_exactly_once_across_the_fanout``
        counts the audit records on a clean ``/tmp``. Neither combines them, and
        the reclaim race only exists when they are combined: the loser of the
        re-link is the copy that can log a second time.

        Note on strength: the interleaving that produces the duplicate is a
        sub-millisecond window between two ``os.link`` calls, so this arm does
        not reliably turn red on unfixed code. It is the end-to-end statement of
        the invariant; the deterministic red-before/green-after proof lives in
        :class:`TestReclaimRaceAfterAStaleReceipt`.
        """
        payload = _write_payload(GATED_CODE_PATH)

        # A receipt from an EARLIER, completed fan-out, under this same call_key.
        SENTINEL.write_text("issue-1641 stale seed")
        assert [d for d, _r in _run_hook_fanout(payload, copies=2)] == ["allow"] * 2
        assert glob.glob(RECEIPT_GLOB), "precondition: a stale receipt is on disk"

        before = _activity_log_line_count()
        SENTINEL.write_text("issue-1641 reclaim race")
        results = _run_hook_fanout(payload, copies=3)
        assert [d for d, _r in results] == ["allow"] * 3, results

        consumed = _consumption_records_since(before)
        assert len(consumed) == 1, (
            f"expected exactly 1 audit record for the second token, got "
            f"{len(consumed)}. A copy that lost the race to reclaim the stale "
            f"receipt fell through to its own consumption instead of deferring "
            f"to the winner: {[e.get('reason') for e in consumed]}"
        )
        assert consumed[0]["reason"] == "issue-1641 reclaim race", consumed[0]
        assert not SENTINEL.exists(), "the second token must be spent exactly once"

    def test_consumption_is_logged_exactly_once_across_the_fanout(self) -> None:
        """N copies, one token, one audit record (Issue #1356 / #1408)."""
        before = _activity_log_line_count()

        SENTINEL.write_text("issue-1641 audit reason")
        results = _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=3)
        assert [d for d, _r in results] == ["allow"] * 3, results

        assert _activity_log().exists(), "consumption must be logged"
        consumed = _consumption_records_since(before)
        assert len(consumed) == 1, (
            f"expected exactly 1 audit record for 1 token across 3 copies, got "
            f"{len(consumed)}. Copies that defer to a sibling's receipt consume "
            f"nothing and must therefore log nothing."
        )
        assert consumed[0]["reason"] == "issue-1641 audit reason", consumed[0]
        assert consumed[0]["sentinel_age_seconds"] >= 0, (
            "sentinel age must still be recorded — the log must run BEFORE unlink"
        )


# ---------------------------------------------------------------------------
# One-shot semantics — the FORBIDDEN alternative fix.
# ---------------------------------------------------------------------------


class TestStillOneShot:
    """Sibling coordination must not extend the token to a LATER tool call."""

    def test_sequential_second_write_is_refused_again(self) -> None:
        SENTINEL.write_text("issue-1641 one-shot")
        first_decision, first_reason = _run_hook(_write_payload(GATED_CODE_PATH))
        assert first_decision == "allow", first_reason
        assert not SENTINEL.exists()

        second_decision, second_reason = _run_hook(_write_payload(GATED_CODE_PATH))
        assert second_decision == "deny", (
            "A one-shot escape hatch was converted into a persistent one: an "
            "identical Write issued AFTER the first one completed was allowed "
            "for free. Reason: " + second_reason
        )
        assert "requires the /implement pipeline" in second_reason

    def test_sequential_write_after_a_fanout_is_refused_again(self) -> None:
        """The receipt left by a fan-out must not buy the next tool call."""
        SENTINEL.write_text("issue-1641 one-shot after fan-out")
        assert [d for d, _r in _run_hook_fanout(_write_payload(GATED_CODE_PATH), 3)] == [
            "allow"
        ] * 3
        assert glob.glob(RECEIPT_GLOB), "the fan-out should have left a receipt"

        decision, reason = _run_hook(_write_payload(GATED_CODE_PATH))
        assert decision == "deny", (
            "A receipt from a completed fan-out granted a bypass to a later, "
            "separate tool call. Reason: " + reason
        )


# ---------------------------------------------------------------------------
# Non-regression for commit f2d841ff (Issue #1638).
# ---------------------------------------------------------------------------


class TestIssue1638BehaviourPreserved:
    """The half that already worked must keep working."""

    def test_intervening_bash_call_still_leaves_the_token_intact(self) -> None:
        SENTINEL.write_text("issue-1641 cross-gate")
        _run_hook_fanout(_bash_payload("ls -la /tmp/skip_write_pipeline_gate"), copies=2)
        assert SENTINEL.exists(), (
            "a Bash call consumed the write-gate token — the Issue #1638 defect "
            "shape has returned"
        )
        results = _run_hook_fanout(_write_payload(GATED_CODE_PATH), copies=2)
        assert [d for d, _r in results] == ["allow"] * 2, results
        assert not SENTINEL.exists()

    def test_ungated_doc_write_consumes_nothing_even_in_a_fanout(self) -> None:
        """Nothing was refused, so nothing may be bought."""
        SENTINEL.write_text("issue-1641 intra-gate")
        results = _run_hook_fanout(_write_payload(UNGATED_DOC_PATH), copies=3)
        assert [d for d, _r in results] == ["allow"] * 3, results
        assert SENTINEL.exists(), (
            "a Write to README.md — which the gate allows unconditionally — "
            "consumed the operator's one-shot bypass"
        )
        assert not glob.glob(RECEIPT_GLOB), "no receipt for a call that bought nothing"


# ---------------------------------------------------------------------------
# The discriminator, tested directly. Both arms.
# ---------------------------------------------------------------------------


class TestReceiptDiscriminator:
    """`_read_write_gate_bypass_receipt` must PERMIT siblings and REFUSE the rest."""

    @staticmethod
    def _plant(call_key: str, *, pid: int, age_seconds: float) -> Path:
        receipt = upt._write_gate_bypass_receipt_path(call_key)
        receipt.write_text(json.dumps({"pid": pid, "consumed_at": time.time()}))
        stamp = time.time() - age_seconds
        os.utime(receipt, (stamp, stamp))
        return receipt

    def test_permits_a_concurrent_sibling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERMITTING arm: another process, and we started before it spent it."""
        key = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "z")
        self._plant(key, pid=os.getpid() + 1, age_seconds=0.0)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)
        assert upt._read_write_gate_bypass_receipt(key) is True

    def test_refuses_a_receipt_written_before_this_process_started(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING arm: a later tool call cannot have started before the spend."""
        key = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "z")
        self._plant(key, pid=os.getpid() + 1, age_seconds=5.0)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time())
        assert upt._read_write_gate_bypass_receipt(key) is False

    def test_refuses_its_own_authors_receipt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING arm: a receipt never grants its own writer a second shot."""
        key = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "z")
        self._plant(key, pid=os.getpid(), age_seconds=0.0)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)
        assert upt._read_write_gate_bypass_receipt(key) is False

    def test_refuses_and_removes_a_stale_receipt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING arm: beyond the TTL a receipt is garbage, not a grant."""
        key = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "z")
        receipt = self._plant(
            key,
            pid=os.getpid() + 1,
            age_seconds=upt.WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS + 10.0,
        )
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", 0.0)
        assert upt._read_write_gate_bypass_receipt(key) is False
        assert not receipt.exists(), "a stale receipt must be swept, not left to rot"

    def test_refuses_when_no_receipt_exists(self) -> None:
        key = upt._write_gate_bypass_call_key("Write", "/nothing/here.py", "", "z")
        assert upt._read_write_gate_bypass_receipt(key) is False


class TestLiveGateEntryPointBothArms:
    """Direct calls on the functions the deployed hook actually runs.

    The subprocess fan-out above is the only way to reproduce a multi-process
    race, but it is still a RECONSTRUCTION of the PreToolUse payload — which is
    precisely where the previous pipeline's verification went wrong. These arms
    call the live functions themselves, with a positive and a negative control
    each, so the mechanism is watched permitting AND refusing without any
    payload replay in between.

    The entry point is ``_check_write_pipeline_required`` — the function the
    fast path calls at ``unified_pre_tool.py`` line ~8289 — not a sub-helper.
    """

    @staticmethod
    def _plant_sibling_receipt(call_key: str) -> Path:
        """Plant the receipt a concurrent sibling would have left behind."""
        receipt = upt._write_gate_bypass_receipt_path(call_key)
        receipt.write_text(json.dumps({"pid": os.getpid() + 1, "consumed_at": time.time()}))
        return receipt

    @staticmethod
    def _force_gated(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_scratch_path", lambda _p: False)
        monkeypatch.setattr(upt, "_is_gated_repo_source", lambda _p: True)

    def test_gate_permits_when_a_sibling_already_spent_the_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERMITTING arm: this is exactly what the refusing copy must now do.

        No sentinel on disk (the sibling consumed it), yet the gate must return
        ``operator_bypass`` rather than the ``full`` tier that produced the
        reported ``Tier: full`` denial.
        """
        self._force_gated(monkeypatch)
        target = "/home/user/app/service.py"
        body = "\n".join(f"def f{i}(): pass" for i in range(30))
        key = upt._write_gate_bypass_call_key("Write", target, "", body)
        self._plant_sibling_receipt(key)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)

        assert not SENTINEL.exists(), "precondition: the sibling consumed it"
        block, tier, _directive = upt._check_write_pipeline_required(
            "Write", target, "", body
        )
        assert (block, tier) == (False, "operator_bypass"), (
            f"the live gate refused a write a concurrent sibling had already "
            f"paid for (block={block}, tier={tier!r})"
        )

    def test_gate_refuses_when_the_receipt_is_not_a_siblings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING arm — a DIFFERENT shape from the reproducer.

        Same planted receipt, same absent sentinel; only the process start time
        moves, so this stands for every later tool call rather than for the one
        that happened to be reported.
        """
        self._force_gated(monkeypatch)
        target = "/home/user/app/service.py"
        body = "\n".join(f"def f{i}(): pass" for i in range(30))
        key = upt._write_gate_bypass_call_key("Write", target, "", body)
        self._plant_sibling_receipt(key)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() + 1.0)

        block, tier, directive = upt._check_write_pipeline_required(
            "Write", target, "", body
        )
        assert block is True, (
            f"a receipt from a completed tool call bought a free bypass "
            f"(tier={tier!r}) — the one-shot became persistent"
        )
        assert tier != "operator_bypass"
        assert directive, "a refusal must carry a REQUIRED NEXT ACTION"

    def test_consume_defers_to_a_sibling_without_logging_a_second_time(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A copy that consumes nothing must record nothing (Issue #1356)."""
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        key = upt._write_gate_bypass_call_key("Write", "/x/y.py", "", "z")
        self._plant_sibling_receipt(key)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)

        assert upt._consume_write_gate_bypass("/x/y.py", call_key=key) is True
        log_file = (
            tmp_path / ".claude" / "logs" / "activity" / f"{time.strftime('%Y-%m-%d')}.jsonl"
        )
        assert not log_file.exists(), (
            "a deferring copy logged a consumption it never made"
        )

    def test_claim_is_won_once_then_deferred(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both arms of the atomic claim, which is what keeps the log singular."""
        key = upt._write_gate_bypass_call_key("Write", "/x/claim.py", "", "z")
        assert upt._claim_write_gate_bypass_receipt(key, "/x/claim.py") == "won"

        # A sibling arriving after the winner: different pid, started earlier.
        receipt = upt._write_gate_bypass_receipt_path(key)
        record = json.loads(receipt.read_text())
        record["pid"] = os.getpid() + 1
        receipt.write_text(json.dumps(record))
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)
        assert upt._claim_write_gate_bypass_receipt(key, "/x/claim.py") == "deferred"

    def test_stale_receipt_does_not_block_a_fresh_claim(self) -> None:
        """Negative control for the claim: a dead receipt is swept, not honoured."""
        key = upt._write_gate_bypass_call_key("Write", "/x/stale.py", "", "z")
        receipt = upt._write_gate_bypass_receipt_path(key)
        receipt.write_text(json.dumps({"pid": os.getpid() + 1, "consumed_at": 0}))
        stamp = time.time() - (upt.WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS + 60)
        os.utime(receipt, (stamp, stamp))
        assert upt._claim_write_gate_bypass_receipt(key, "/x/stale.py") == "won"


class TestReclaimRaceAfterAStaleReceipt:
    """The second link attempt must re-check, not unlink whatever it collides with.

    The interleaving: a stale receipt from an EARLIER call is on disk under this
    call_key, and two genuinely fresh siblings race to reclaim it. Both correctly
    judge it a non-sibling and both sweep it; one of them then wins the re-link
    and becomes the true winner. The loser's SECOND ``os.link`` now collides with
    a receipt that is legitimate. If the sibling re-check is skipped on that
    attempt, the loser unlinks the winner's live receipt and reports
    ``"unavailable"`` — which is not ``"deferred"``, so it falls through and logs
    a second consumption for one token.

    Timing that narrow is not reproducible by starting processes, so the arms
    below drive it deterministically by injecting the sibling's receipt into the
    window between the two attempts.
    """

    @staticmethod
    def _plant_stale(call_key: str) -> Path:
        """A receipt from an EARLIER consumption: our own pid, so not a sibling."""
        receipt = upt._write_gate_bypass_receipt_path(call_key)
        receipt.write_text(json.dumps({"pid": os.getpid(), "consumed_at": time.time()}))
        return receipt

    @staticmethod
    def _link_that_plants_on_the_second_attempt(
        monkeypatch: pytest.MonkeyPatch, record: dict[str, Any]
    ) -> None:
        """Make the 2nd ``os.link`` collide with ``record`` instead of nothing.

        The 1st call collides with the planted stale receipt for real. Before the
        2nd call, ``record`` is published at the destination — standing in for
        the racer that swept the same stale receipt and won the re-link.
        """
        real_link = os.link
        calls = {"n": 0}

        def fake_link(src: str, dst: str) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                Path(dst).write_text(json.dumps(record))
            real_link(src, dst)  # raises FileExistsError — the collision

        monkeypatch.setattr(os, "link", fake_link)

    def test_a_sibling_that_wins_the_reclaim_race_is_deferred_to_not_unlinked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERMITTING arm: a legitimate receipt at attempt 2 must be honoured."""
        key = upt._write_gate_bypass_call_key("Write", "/x/reclaim.py", "", "z")
        receipt = self._plant_stale(key)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)
        winner = {"pid": os.getpid() + 1, "consumed_at": time.time()}
        self._link_that_plants_on_the_second_attempt(monkeypatch, winner)

        verdict = upt._claim_write_gate_bypass_receipt(key, "/x/reclaim.py")

        assert verdict == "deferred", (
            f"The loser of a reclaim race returned {verdict!r} instead of "
            f"'deferred'. Only 'deferred' short-circuits _consume_write_gate_bypass; "
            f"anything else falls through and logs a SECOND "
            f"write_gate_operator_bypass_consumed record for one token."
        )
        assert receipt.exists(), (
            "the loser unlinked the winning sibling's live receipt — every copy "
            "still to arrive in this fan-out will now find nothing and refuse"
        )
        assert json.loads(receipt.read_text())["pid"] == winner["pid"], (
            "the receipt on disk is no longer the winner's"
        )

    def test_a_non_sibling_receipt_at_the_second_attempt_is_still_swept(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING arm: re-checking must not become a blanket defer.

        Same interleaving, but what lands in the window is another dead receipt
        (written by this very process, so it can never be a sibling). It must be
        swept exactly as before — otherwise the fix would hand a free bypass to
        any file that happens to occupy the name.
        """
        key = upt._write_gate_bypass_call_key("Write", "/x/reclaim_dead.py", "", "z")
        receipt = self._plant_stale(key)
        monkeypatch.setattr(upt, "_HOOK_PROCESS_START_TIME", time.time() - 30.0)
        self._link_that_plants_on_the_second_attempt(
            monkeypatch, {"pid": os.getpid(), "consumed_at": time.time()}
        )

        verdict = upt._claim_write_gate_bypass_receipt(key, "/x/reclaim_dead.py")

        assert verdict == "unavailable", (
            f"a receipt that fails the sibling test bought a 'deferred' "
            f"(got {verdict!r}) — the re-check must consult the discriminator, "
            f"not merely observe that a file exists"
        )
        assert not receipt.exists(), "a dead receipt must still be swept"


class TestCallKeyIdentity:
    """The key must identify a logical tool call — same call same key, else not."""

    def test_identical_payloads_produce_the_same_key(self) -> None:
        a = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "content")
        b = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "content")
        assert a == b

    @pytest.mark.parametrize(
        "args",
        [
            ("Edit", "/a/b.py", "", "content"),
            ("Write", "/a/other.py", "", "content"),
            ("Write", "/a/b.py", "old", "content"),
            ("Write", "/a/b.py", "", "different"),
        ],
    )
    def test_any_differing_field_produces_a_different_key(
        self, args: tuple[str, str, str, str]
    ) -> None:
        baseline = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "content")
        assert upt._write_gate_bypass_call_key(*args) != baseline

    def test_key_is_not_derived_from_session_id(self) -> None:
        """Session id is not guaranteed identical between concurrent copies.

        Locking the signature keeps a future refactor from smuggling it in and
        silently un-fixing the fan-out.
        """
        import inspect

        params = list(
            inspect.signature(upt._write_gate_bypass_call_key).parameters
        )
        assert params == ["tool_name", "file_path", "old_string", "new_string"], params


# ---------------------------------------------------------------------------
# Structural lock — the single-consumption-site invariant survives the repair.
# ---------------------------------------------------------------------------


def test_receipt_path_is_derived_from_the_sentinel_constant() -> None:
    """No second literal may name the sentinel — each one is a candidate consumer."""
    source = HOOK_SOURCE.read_text()
    assert source.count('Path("/tmp/skip_write_pipeline_gate")') == 1, (
        "The write-gate sentinel path is constructed more than once."
    )
    assert source.count("skip_file.unlink()") == 1, (
        "More than one site unlinks the write-gate sentinel. Route all "
        "consumption through _consume_write_gate_bypass."
    )
    key = upt._write_gate_bypass_call_key("Write", "/a/b.py", "", "z")
    receipt = upt._write_gate_bypass_receipt_path(key)
    assert receipt.parent == upt.WRITE_GATE_BYPASS_SENTINEL.parent
    assert receipt != upt.WRITE_GATE_BYPASS_SENTINEL
    assert key in receipt.name
