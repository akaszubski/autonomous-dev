"""The repo opt-out must not be reported as a guard failing open (Issue #1685).

``.claude/.bypass`` is the SUPPORTED durable per-repo opt-out (CLAUDE.md).
Before this fix ``proof_of_block.py`` printed ``bypass : present`` in its
header and then ignored it in every verdict, so an ordinary gate that was
deliberately inert was labelled ``FAILS-OPEN`` / ``FAILS OPEN SILENTLY`` --
identical to a guard that genuinely broke under fault. Measured in spektiv
(committed ``.bypass``, 17 Jun): ``write-pipeline-gate`` reported FAILS-OPEN
with the hook's own reason reading ``Universal bypass active (#969)``.

Two consequences, the second worse: the silent count is inflated in every
opted-out repo, and a GENUINE fail-open there becomes indistinguishable from
the opt-out. The goal's abort condition 3 reads that count, so an abort
trigger could fire on correct behaviour.

Every test here is watched BOTH ways. The relabel is only trustworthy if it
also declines to fire: each bypassed case is paired with an identical
non-bypassed case that must still report the genuine failure, and with a
denying case that must keep its REFUSES/PROVEN label (the #1435 hard floor's
shape -- the exemption must not be swept into the new category).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# tests/unit/scripts/test_x.py -> scripts -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "scripts" / "proof_of_block.py"

sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "scripts"))

import proof_of_block  # noqa: E402
from proof_of_block import (  # noqa: E402
    BYPASS_ABSENT,
    BYPASS_COMMITTED,
    BYPASS_UNCOMMITTED,
    NOT_ENFORCED,
    NOT_ENFORCED_OUTCOME,
    REFUSES,
    SILENT,
    compute_exit_code,
    describe_bypass,
    env_bypass_note,
    log_activity_row,
    not_enforced_set,
    run_fault,
    run_guard,
    scenario_bypassed,
    silent_set,
    split_no_longer_silent,
)

BYPASS_ENV_VAR = "AUTONOMOUS_DEV_BYPASS"

# A dependency name the synthetic hooks below import so the shim has something
# real to break. Matched by module NAME in the shim's finder, so it fires
# whether or not the file exists.
STUB_DEP = "pob_stub_dep"

STUB_FAULT = {
    "id": f"import_raises:{STUB_DEP}",
    "kind": "import_raises",
    "module": STUB_DEP,
    "what": "the synthetic hook's only dependency raises ImportError",
    "touches": "the synthetic hook imports it before deciding",
}


# ---------------------------------------------------------------------------
# builders -- synthetic hooks, driven end-to-end exactly like the real ones
# ---------------------------------------------------------------------------

_SYNTHETIC_HOOK = '''\
import json, sys
try:
    import {dep}          # the shim breaks THIS
    _dep_ok = True
except ImportError:
    _dep_ok = False       # swallowed silently -- the #1471 shape
sys.stdin.read()
decision = "{decision}" if _dep_ok else "{degraded}"
print(json.dumps({{"hookSpecificOutput": {{
    "hookEventName": "PreToolUse", "permissionDecision": decision,
    "permissionDecisionReason": "synthetic #1685 control"}}}}))
'''


def _write_hook(hooks_dir: Path, name: str, *, decision: str,
                degraded: str) -> Path:
    """Write a synthetic single-file hook with a known decision shape."""
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / name
    hook.write_text(_SYNTHETIC_HOOK.format(dep=STUB_DEP, decision=decision,
                                           degraded=degraded))
    (hooks_dir / f"{STUB_DEP}.py").write_text("VALUE = 1\n")
    return hook


def _fixture_factory(base: Path, *, bypassed: bool):
    """Return a proof_of_block-style fixture callable.

    Args:
        base: Directory the fixture roots live under.
        bypassed: Whether to plant ``.claude/.bypass`` in the fixture root.
    """
    counter = {"n": 0}

    def build(root: Path) -> Path:
        counter["n"] += 1
        target = base / f"fx{counter['n']}"
        (target / ".claude").mkdir(parents=True, exist_ok=True)
        (target / "src").mkdir(exist_ok=True)
        if bypassed:
            (target / ".claude" / ".bypass").write_text("")
        return target

    return build


def _spec(base: Path, *, hook_name: str, bypassed: bool) -> dict:
    return {
        "guard": "synthetic-1685",
        "issue": "#1685",
        "hook": hook_name,
        "fixture": _fixture_factory(base, bypassed=bypassed),
        "positive": {
            "why": "the synthetic bad case must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {"file_path": str(r / "src" / "a.py"),
                                     "content": "x = 1\n"},
        },
        "negative": {
            "why": "the synthetic legitimate case must be permitted",
            "tool_name": "Read",
            "tool_input": lambda r: {"file_path": str(r / "src" / "a.py")},
        },
        "fault": STUB_FAULT,
    }


def _guard_result(name: str, verdict: str = "PROVEN",
                  fault: str | None = None) -> dict:
    out = {"guard": name, "issue": "#0", "hook": "h.py", "verdict": verdict}
    if fault is not None:
        out["fault"] = {"fault": "synthetic", "outcome": fault}
    return out


# ---------------------------------------------------------------------------
# 1. scenario_bypassed -- read through hook_bypass, per scenario, both arms
# ---------------------------------------------------------------------------

def test_scenario_bypassed_sees_a_flag_in_the_scenario_root(tmp_path: Path) -> None:
    """REFUSING arm: a scenario rooted under a .bypass is reported bypassed."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".bypass").write_text("")
    assert scenario_bypassed(tmp_path) is True


def test_scenario_bypassed_is_false_without_a_flag(tmp_path: Path) -> None:
    """PERMITTING arm. Without this control the function could be a constant
    ``True`` and every test above it would still pass."""
    (tmp_path / ".claude").mkdir()
    assert scenario_bypassed(tmp_path) is False


def test_scenario_bypassed_sees_a_flag_in_an_ancestor(tmp_path: Path) -> None:
    """The hook walks up from its cwd, so this harness must too."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".bypass").write_text("")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert scenario_bypassed(deep) is True


def test_scenario_bypassed_ignores_the_operators_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The env arm governs nothing here and must not relabel anything.

    ``drive_raw`` strips ``AUTONOMOUS_DEV_BYPASS`` from every hook subprocess,
    so a hook never sees it. Consulting ``is_bypassed()`` unfiltered would
    relabel every genuine fail-open as a repo opt-out on any machine whose
    shell exports the variable -- a probe reporting the operator's environment
    instead of the system under test.
    """
    monkeypatch.setenv(BYPASS_ENV_VAR, "1")
    (tmp_path / ".claude").mkdir()
    assert scenario_bypassed(tmp_path) is False


def test_scenario_bypassed_restores_the_env_var_it_neutralised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It pops the variable to answer; leaving it popped would silently
    disable the operator's own bypass for the rest of the process."""
    monkeypatch.setenv(BYPASS_ENV_VAR, "keep-me")
    scenario_bypassed(tmp_path)
    assert proof_of_block.os.environ.get(BYPASS_ENV_VAR) == "keep-me"


def test_harness_reads_bypass_through_hook_bypass_not_a_private_copy() -> None:
    """ONE reader of the rule. A local ``.exists()`` on the flag file is a
    SECOND implementation of a rule that already has one."""
    source = SCRIPT_PATH.read_text()
    assert "from hook_bypass import" in source
    assert '".bypass"' not in source, (
        'proof_of_block must not name .claude/.bypass itself -- '
        "hook_bypass owns that path"
    )


# ---------------------------------------------------------------------------
# 2. describe_bypass -- committed and uncommitted must not be merged (#1434)
# ---------------------------------------------------------------------------

def _git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "."], cwd=str(root),
                   capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(root),
                   capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root),
                   capture_output=True, check=False)
    return root


def test_describe_bypass_absent(tmp_path: Path) -> None:
    state = describe_bypass(_git_repo(tmp_path / "r"))
    assert state["active"] is False
    assert state["form"] == BYPASS_ABSENT
    assert state["path"] is None


def test_describe_bypass_uncommitted_is_the_emergency_hatch(tmp_path: Path) -> None:
    root = _git_repo(tmp_path / "r")
    (root / ".claude").mkdir()
    (root / ".claude" / ".bypass").write_text("")
    state = describe_bypass(root)
    assert state["active"] is True
    assert state["form"] == BYPASS_UNCOMMITTED


def test_describe_bypass_committed_is_the_durable_opt_out(tmp_path: Path) -> None:
    """The spektiv shape: git-tracked, therefore a policy decision.

    Paired with the test above, this is the control that the two forms are
    actually distinguished -- a function returning a constant form would pass
    one of these and fail the other.
    """
    root = _git_repo(tmp_path / "r")
    (root / ".claude").mkdir()
    flag = root / ".claude" / ".bypass"
    flag.write_text("")
    subprocess.run(["git", "add", "-f", ".claude/.bypass"], cwd=str(root),
                   capture_output=True, check=False)
    subprocess.run(["git", "commit", "-qm", "opt out"], cwd=str(root),
                   capture_output=True, check=False)
    state = describe_bypass(root)
    assert state["active"] is True
    assert state["form"] == BYPASS_COMMITTED
    assert state["path"] == str(flag)


def test_env_bypass_note_reports_a_neutralised_env_var(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(BYPASS_ENV_VAR, raising=False)
    assert env_bypass_note() is None
    monkeypatch.setenv(BYPASS_ENV_VAR, "1")
    note = env_bypass_note()
    assert note is not None and "STRIPPED" in note


# ---------------------------------------------------------------------------
# 3. the verdict arm -- end-to-end through run_guard, both ways
# ---------------------------------------------------------------------------

def test_run_guard_reports_a_genuine_fail_open_when_no_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix must NOT relabel genuine failures.

    A synthetic guard that allows the bad case in a repo with no opt-out is
    still FAILS-OPEN. This is the negative control for the whole change.
    """
    hooks = tmp_path / "hooks"
    _write_hook(hooks, "always_allow.py", decision="allow", degraded="allow")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="always_allow.py", bypassed=False)

    result = run_guard(spec, with_fault=False)

    assert result["verdict"] == "FAILS-OPEN"
    assert result["positive"]["bypassed"] is False


def test_run_guard_relabels_a_fail_open_under_an_active_opt_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The arm that was wrong: same hook, same action, opted-out repo."""
    hooks = tmp_path / "hooks"
    _write_hook(hooks, "always_allow.py", decision="allow", degraded="allow")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="always_allow.py", bypassed=True)

    result = run_guard(spec, with_fault=False)

    assert result["verdict"] == NOT_ENFORCED
    assert result["positive"]["bypassed"] is True
    # Requirement 4: the limitation is STATED, not silently resolved.
    assert "not distinguishable" in result["detail"]


def test_run_guard_keeps_proven_for_a_guard_that_denies_under_a_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control for the #1435 hard floor: the exemption must not be swept in.

    A guard that still REFUSES under an active bypass is the strongest result
    in the run. Folding it into the opt-out bucket would erase it. Measured in
    spektiv: six guards keep REFUSES with a committed .bypass present.
    """
    hooks = tmp_path / "hooks"
    _write_hook(hooks, "hard_floor.py", decision="deny", degraded="deny")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="hard_floor.py", bypassed=True)
    # Its negative arm must permit, so drive it against the allowing hook.
    spec["negative"] = {
        "why": "unused for this control",
        "tool_name": "Read",
        "tool_input": lambda r: {"file_path": str(r / "src" / "a.py")},
    }

    result = run_guard(spec, with_fault=False)

    # Positive denied -> the bypass branch is never reached at all.
    assert result["positive"]["ok"] is True
    assert result["verdict"] in ("PROVEN", "OVER-BLOCKS")
    assert result["verdict"] != NOT_ENFORCED


# ---------------------------------------------------------------------------
# 4. the fault arm -- classification, both ways
# ---------------------------------------------------------------------------

def test_run_fault_reports_silent_when_no_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence 4: a synthetic guard that GENUINELY fails open in a
    non-bypassed repo is still FAILS OPEN SILENTLY."""
    hooks = tmp_path / "hooks"
    hook = _write_hook(hooks, "degrades.py", decision="deny", degraded="allow")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="degrades.py", bypassed=False)

    fault = run_fault(spec, hook)

    assert fault["outcome"] == SILENT, fault
    assert fault["bypassed"] is False
    assert "raw_outcome" not in fault


def test_run_fault_relabels_a_silent_fail_open_under_an_active_opt_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same hook, same injected fault, opted-out repo -> not a finding.

    The raw classification is PRESERVED rather than discarded: hiding it would
    trade a false positive for a blind spot.
    """
    hooks = tmp_path / "hooks"
    hook = _write_hook(hooks, "degrades.py", decision="deny", degraded="allow")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="degrades.py", bypassed=True)

    fault = run_fault(spec, hook)

    assert fault["outcome"] == NOT_ENFORCED_OUTCOME, fault
    assert fault["raw_outcome"] == SILENT
    assert fault["bypassed"] is True
    assert "NOT distinguishable" in fault["trace"]


def test_run_fault_keeps_refuses_under_an_active_opt_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REFUSES is never rewritten -- the hard-floor control, fault-arm side."""
    hooks = tmp_path / "hooks"
    hook = _write_hook(hooks, "hard_floor.py", decision="deny", degraded="deny")
    monkeypatch.setattr(proof_of_block, "HOOKS", hooks)
    spec = _spec(tmp_path / "fx", hook_name="hard_floor.py", bypassed=True)

    fault = run_fault(spec, hook)

    assert fault["outcome"] == REFUSES, fault
    assert fault["bypassed"] is True


# ---------------------------------------------------------------------------
# 5. the counts stay separate
# ---------------------------------------------------------------------------

def test_silent_set_excludes_opted_out_guards() -> None:
    """Only genuine fail-opens feed the ratchet, the FINDING line and the
    goal's abort threshold."""
    results = [
        _guard_result("genuine", fault=SILENT),
        _guard_result("opted-out", NOT_ENFORCED, fault=NOT_ENFORCED_OUTCOME),
    ]
    assert silent_set(results) == {"genuine"}


def test_not_enforced_set_reports_them_separately() -> None:
    results = [
        _guard_result("genuine", fault=SILENT),
        _guard_result("opted-out", NOT_ENFORCED, fault=NOT_ENFORCED_OUTCOME),
    ]
    assert not_enforced_set(results) == {"opted-out"}


def test_not_enforced_set_catches_a_verdict_only_case() -> None:
    """``--no-fault`` records no fault outcome, so the verdict must count."""
    results = [_guard_result("opted-out", NOT_ENFORCED)]
    assert not_enforced_set(results) == {"opted-out"}


def test_not_enforced_set_is_empty_without_an_opt_out() -> None:
    """The permitting arm: it must not label an ordinary run."""
    results = [_guard_result("a"), _guard_result("b", fault=SILENT)]
    assert not_enforced_set(results) == set()


# ---------------------------------------------------------------------------
# 6. exit status reflects genuine failures only
# ---------------------------------------------------------------------------

def test_exit_code_zero_when_an_opted_out_guard_is_inert() -> None:
    """The spektiv shape: 7 PROVEN + 1 NOT-ENFORCED must exit 0.

    A permanently red check in every opted-out repo trains its readers to
    ignore the whole class of signal.
    """
    results = [_guard_result(f"g{i}") for i in range(7)]
    results.append(_guard_result("opted-out", NOT_ENFORCED))
    assert compute_exit_code(results, {"ok": True}) == 0


def test_exit_code_one_when_a_guard_genuinely_fails_open() -> None:
    """Unchanged polarity: FAILS-OPEN still gates."""
    results = [_guard_result(f"g{i}") for i in range(7)]
    results.append(_guard_result("broken", "FAILS-OPEN"))
    assert compute_exit_code(results, {"ok": True}) == 1


def test_exit_code_one_when_nothing_was_proven() -> None:
    """Anti-vacuity floor: an all-NOT-ENFORCED run observed no guard refusing
    anything, so it is not a pass however it got there."""
    results = [_guard_result(f"g{i}", NOT_ENFORCED) for i in range(8)]
    assert compute_exit_code(results, {"ok": True}) == 1


# ---------------------------------------------------------------------------
# 7. the ratchet must not read an opt-out as a recovery
# ---------------------------------------------------------------------------

def test_split_no_longer_silent_calls_an_opted_out_guard_unmeasured() -> None:
    """Re-recording a baseline on this would pin an absence as a fix."""
    results = [_guard_result("g", NOT_ENFORCED, fault=NOT_ENFORCED_OUTCOME)]
    went_unmeasured, recovered = split_no_longer_silent({"g"}, results)
    assert went_unmeasured == {"g"}
    assert recovered == set()


def test_split_no_longer_silent_still_reports_a_real_recovery() -> None:
    """The permitting arm: a guard that now REFUSES really did recover."""
    results = [_guard_result("g", "PROVEN", fault=REFUSES)]
    went_unmeasured, recovered = split_no_longer_silent({"g"}, results)
    assert went_unmeasured == set()
    assert recovered == {"g"}


def test_split_no_longer_silent_separates_a_mixed_set() -> None:
    """Both causes in one run must land in different buckets -- the case a
    single count would collapse."""
    results = [
        _guard_result("fixed", "PROVEN", fault=REFUSES),
        _guard_result("inert", NOT_ENFORCED, fault=NOT_ENFORCED_OUTCOME),
    ]
    went_unmeasured, recovered = split_no_longer_silent(
        {"fixed", "inert"}, results)
    assert went_unmeasured == {"inert"}
    assert recovered == {"fixed"}


# ---------------------------------------------------------------------------
# 8. the machine reader gets both numbers
# ---------------------------------------------------------------------------

def test_activity_row_separates_the_two_counts(tmp_path: Path) -> None:
    """A reader counting silent fail-opens against the abort threshold must
    never have to subtract opted-out guards, nor accidentally include them."""
    results = [
        _guard_result("genuine", fault=SILENT),
        _guard_result("opted-out", NOT_ENFORCED, fault=NOT_ENFORCED_OUTCOME),
    ]
    written = log_activity_row(tmp_path, results, 0)
    assert written is not None
    row = json.loads(written.read_text().splitlines()[-1])
    assert row["silent"] == ["genuine"]
    assert row["not_enforced"] == ["opted-out"]
    assert row["bypass"] == BYPASS_ABSENT
