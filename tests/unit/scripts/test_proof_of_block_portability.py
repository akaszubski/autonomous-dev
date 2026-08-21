"""Portability, exit-floor and silent-set-ratchet tests for proof_of_block.

Implements Issue #1586. ``proof_of_block.py`` is the only artifact in this repo
that demonstrates a guard REFUSING the bad case and PERMITTING the legitimate
one. Before #1586 it ran in 0 CI jobs, 0 hooks and 0 tests, and lived in a
top-level ``scripts/`` directory the install manifest does not deploy -- so
enforcement was observable here and unobservable in every consumer repo.

These tests protect the three things that port can break:

1. The exit floor stays RUNTIME-ENUMERATED. An earlier session nearly replaced
   ``proven == len(results)`` with a literal ``7``.
   ``test_compute_exit_code_three_guards_all_proven_is_the_anti_substitution_control``
   is the control: three all-PROVEN guards exit 0, which a hardcoded 7 cannot do.
2. The path pins stay resolved at runtime, in both the source and installed
   layouts.
3. The silent-set ratchet is watched BOTH ways -- refusing a newly-silent guard
   and permitting a shrinking silent set -- and refuses to run at all against a
   baseline with no fault data, which would pass vacuously.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# tests/unit/scripts/test_x.py -> scripts -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "scripts" / "proof_of_block.py"
MANIFEST_PATH = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "install_manifest.json"
)

sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "scripts"))

import proof_of_block  # noqa: E402
from proof_of_block import (  # noqa: E402
    HOOKS,
    REPO,
    SESSION_TAG,
    SILENT,
    UNVERIFIED_INJECTION,
    _adev_repo,
    _first_real_repo_guard,
    _plan_exited,
    _real_repo,
    compare_silent_set,
    compute_exit_code,
    drive_raw,
    hooks_dir_candidates,
    log_activity_row,
    resolve_artifacts_dir,
    resolve_hooks_dir,
    silent_set,
)

UNIFIED_PRE_TOOL = HOOKS / "unified_pre_tool.py"

# A session id that is NOT the probe's tag -- i.e. the shape a real in-flight
# session writes into the sentinel. The whole of Defect 1 turns on the hook
# treating a MISMATCH as permission to delete.
FOREIGN_SESSION_ID = "b6d5e4c6-5575-49f2-9781-4ced453c60e8"


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def _guard(name: str, verdict: str = "PROVEN", fault: str | None = None) -> dict:
    """Build a synthetic per-guard result dict."""
    out = {"guard": name, "issue": "#0", "hook": "h.py", "verdict": verdict}
    if fault is not None:
        out["fault"] = {"fault": "synthetic", "outcome": fault}
    return out


def _healthy_instrument() -> dict:
    return {"ok": True, "scenario": "synthetic"}


def _write_baseline(path: Path, results: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "recorded": "2026-08-21T00:00:00+00:00",
                "commit": "deadbeef",
                "instrument": _healthy_instrument(),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    return path


# ---------------------------------------------------------------------------
# 1. the exit floor -- runtime-enumerated, never a literal
# ---------------------------------------------------------------------------

def test_compute_exit_code_three_guards_all_proven_is_the_anti_substitution_control() -> None:
    """THREE all-PROVEN guards must exit 0.

    This is the anti-substitution control for Issue #1586. A hardcoded floor of
    7 (``proven == 7``) returns 1 here, so this test fails the moment the
    runtime-enumerated floor is replaced by a literal.
    """
    results = [_guard("a"), _guard("b"), _guard("c")]
    assert compute_exit_code(results, _healthy_instrument()) == 0


def test_compute_exit_code_seven_guards_all_proven() -> None:
    results = [_guard(f"g{i}") for i in range(7)]
    assert compute_exit_code(results, _healthy_instrument()) == 0


def test_compute_exit_code_one_fails_open_among_seven() -> None:
    """The PERMITTING arm of the exit floor's counterpart: it must refuse."""
    results = [_guard(f"g{i}") for i in range(6)] + [_guard("bad", "FAILS-OPEN")]
    assert compute_exit_code(results, _healthy_instrument()) == 1


def test_compute_exit_code_over_blocks_also_fails() -> None:
    results = [_guard("a"), _guard("b", "OVER-BLOCKS")]
    assert compute_exit_code(results, _healthy_instrument()) == 1


def test_compute_exit_code_unverified_guard_fails() -> None:
    """A missing hook yields UNVERIFIED, which must not count as enforcement."""
    results = [_guard("a"), _guard("missing", "UNVERIFIED")]
    assert compute_exit_code(results, _healthy_instrument()) == 1


def test_compute_exit_code_empty_results_is_not_a_pass() -> None:
    """No vacuous green.

    ``proven == len(results)`` is vacuously true for zero guards. A probe that
    returns zero is not evidence of zero, so an empty run must exit 1.
    """
    assert compute_exit_code([], _healthy_instrument()) == 1
    assert compute_exit_code([], None) == 1


def test_compute_exit_code_broken_instrument_gates() -> None:
    """A broken instrument makes every fault result vacuous, so it must gate."""
    results = [_guard(f"g{i}") for i in range(7)]
    assert compute_exit_code(results, {"ok": False, "scenario": "synthetic"}) == 1


def test_compute_exit_code_injection_unverified_gates() -> None:
    results = [_guard("a"), _guard("b", fault=UNVERIFIED_INJECTION)]
    assert compute_exit_code(results, _healthy_instrument()) == 1


def test_compute_exit_code_silent_fault_does_not_gate() -> None:
    """Exit-code polarity is preserved: fault OUTCOMES never gate.

    Four guards fail open silently in the recorded baseline and the run still
    exits 0. That is deliberate -- the deliverable is the classification, and a
    build break is the wrong response to it. The ratchet, not the exit floor,
    is what catches a NEW silent guard.
    """
    results = [_guard(f"g{i}", fault=SILENT) for i in range(7)]
    assert compute_exit_code(results, _healthy_instrument()) == 0


def test_compute_exit_code_no_fault_mode_ignores_instrument() -> None:
    results = [_guard("a"), _guard("b")]
    assert compute_exit_code(results, None) == 0


# ---------------------------------------------------------------------------
# 2. path resolution -- both layouts
# ---------------------------------------------------------------------------

def test_resolve_hooks_dir_installed_tree(tmp_path: Path) -> None:
    """An INSTALLED copy must test the installed hooks -- the ones that run."""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "scripts").mkdir(parents=True)
    script = tmp_path / ".claude" / "scripts" / "proof_of_block.py"
    script.write_text("#\n")

    assert resolve_hooks_dir(tmp_path, script) == tmp_path / ".claude" / "hooks"


def test_resolve_hooks_dir_source_tree(tmp_path: Path) -> None:
    src = tmp_path / "plugins" / "autonomous-dev"
    (src / "hooks").mkdir(parents=True)
    (src / "scripts").mkdir(parents=True)
    script = src / "scripts" / "proof_of_block.py"
    script.write_text("#\n")

    assert resolve_hooks_dir(tmp_path, script) == src / "hooks"


def test_resolve_hooks_dir_falls_back_to_repo_when_script_is_detached(
    tmp_path: Path,
) -> None:
    """With no sibling hooks dir, resolution falls back to the repo layouts."""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    detached = tmp_path / "elsewhere" / "deep" / "proof_of_block.py"
    detached.parent.mkdir(parents=True)
    detached.write_text("#\n")

    assert resolve_hooks_dir(tmp_path, detached) == tmp_path / ".claude" / "hooks"


def test_resolve_hooks_dir_returns_none_when_unreachable(tmp_path: Path) -> None:
    """Negative control: no hooks anywhere must NOT resolve to something."""
    detached = tmp_path / "elsewhere" / "proof_of_block.py"
    detached.parent.mkdir(parents=True)
    detached.write_text("#\n")

    assert resolve_hooks_dir(tmp_path, detached) is None


def test_hooks_dir_candidates_are_reported_for_the_error_message(
    tmp_path: Path,
) -> None:
    """The exit-2 path prints what it tried, so it must be enumerable."""
    candidates = hooks_dir_candidates(tmp_path, tmp_path / "s" / "x.py")
    assert len(candidates) == 3
    assert tmp_path / ".claude" / "hooks" in candidates
    assert tmp_path / "plugins" / "autonomous-dev" / "hooks" in candidates


def test_resolve_artifacts_dir_without_tests_dir(tmp_path: Path) -> None:
    """A consumer repo has no tests/ -- artifacts still resolve."""
    assert not (tmp_path / "tests").exists()
    assert resolve_artifacts_dir(tmp_path) == tmp_path / ".claude" / "proofs"


def test_resolve_artifacts_dir_ignores_a_present_tests_dir(tmp_path: Path) -> None:
    """One canonical location. A tests/ dir must not change the answer."""
    (tmp_path / "tests" / "proofs").mkdir(parents=True)
    assert resolve_artifacts_dir(tmp_path) == tmp_path / ".claude" / "proofs"


def test_resolve_artifacts_dir_override(tmp_path: Path) -> None:
    override = tmp_path / "somewhere" / "else"
    assert resolve_artifacts_dir(tmp_path, str(override)) == override.resolve()


# ---------------------------------------------------------------------------
# 3. source shape -- the pins must not come back
# ---------------------------------------------------------------------------

def test_source_has_no_fixed_depth_parent_indexing() -> None:
    """``parents[N]`` silently resolves wrong when the file moves or installs
    at a different depth. Issue #1586 removed all of it."""
    source = SCRIPT_PATH.read_text()
    assert "parents[" not in source, (
        "proof_of_block.py must not index into .parents -- it ships to consumer "
        "repos where the depth differs"
    )


def test_source_has_no_tests_proofs_literal() -> None:
    source = SCRIPT_PATH.read_text()
    assert '"tests"' not in source, (
        "artifacts must not key off tests/, which consumer repos may not have"
    )


def test_source_has_no_hardcoded_plugin_path_pin() -> None:
    """The old pin was ``REPO / "plugins" / "autonomous-dev" / "hooks"`` at
    module scope. It may now appear ONLY inside the candidate list."""
    source = SCRIPT_PATH.read_text()
    assert 'HOOKS = REPO /' not in source
    assert 'ARTIFACTS = REPO /' not in source


def test_harness_imports_stdlib_only() -> None:
    """The harness must run in a repo with no pytest and no tests/.

    Its only non-stdlib import is the canonical ``path_utils`` helper from the
    plugin's own lib/, which the manifest deploys alongside it.
    """
    source = SCRIPT_PATH.read_text()
    for forbidden in ("import pytest", "import yaml", "import requests",
                      "import anthropic", "import openai"):
        assert forbidden not in source, f"{forbidden} breaks stdlib-only"


def test_harness_uses_the_canonical_root_helper_not_a_private_copy() -> None:
    """D1: import the sanctioned sink; do not add a third _detect_project_root."""
    source = SCRIPT_PATH.read_text()
    assert "from path_utils import find_project_root" in source
    # A DEFINITION is the anti-pattern; the name may appear in a comment
    # explaining why no third copy was added.
    assert "def _detect_project_root" not in source, (
        "a third copy of the private root detector is the anti-pattern this "
        "change exists to avoid (security_utils.py and alignment_gate.py "
        "already carry one each)"
    )


# ---------------------------------------------------------------------------
# 4. the manifest ships it
# ---------------------------------------------------------------------------

def test_manifest_ships_proof_of_block() -> None:
    """Closes a one-way gap: the existing bootstrap smoke test only checks
    manifest->file, never file->manifest. Without this, the harness could exist
    on disk and still deploy nowhere -- its state before Issue #1586."""
    manifest = json.loads(MANIFEST_PATH.read_text())
    files = manifest["components"]["scripts"]["files"]
    assert "plugins/autonomous-dev/scripts/proof_of_block.py" in files


def test_manifest_scripts_are_sorted() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    files = manifest["components"]["scripts"]["files"]
    assert files == sorted(files), "insert in sorted position"


def test_manifest_scripts_target_is_sibling_of_lib() -> None:
    """The sibling-bridge idiom depends on this: ``<script>/../lib`` only
    resolves in the installed tree because scripts and lib deploy as siblings."""
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["components"]["scripts"]["target"] == ".claude/scripts"
    assert manifest["components"]["lib"]["target"] == ".claude/lib"


def test_old_top_level_script_path_is_gone() -> None:
    assert not (REPO_ROOT / "scripts" / "proof_of_block.py").exists(), (
        "the top-level copy was moved by git mv; two copies would drift"
    )


# ---------------------------------------------------------------------------
# 5. the silent-set ratchet -- watched BOTH ways
# ---------------------------------------------------------------------------

def test_compare_silent_set_refuses_a_newly_silent_guard(tmp_path: Path) -> None:
    """REFUSING arm. A guard that was REFUSES in the baseline and is SILENT now
    must be reported as newly_silent."""
    baseline = _write_baseline(
        tmp_path / "proof-of-block.json",
        [
            _guard("hard-floor", fault="REFUSES"),
            _guard("plan-gate", fault=SILENT),
        ],
    )
    current = [
        _guard("hard-floor", fault=SILENT),   # regressed
        _guard("plan-gate", fault=SILENT),    # unchanged
    ]

    newly_silent, no_longer_silent = compare_silent_set(current, baseline)

    assert newly_silent == {"hard-floor"}
    assert no_longer_silent == set()


def test_compare_silent_set_permits_a_shrinking_silent_set(tmp_path: Path) -> None:
    """PERMITTING arm, authored to a DIFFERENT shape than the refusing case:
    the silent set shrinks rather than grows. It must pass AND name what
    recovered, so the developer knows to re-record the pin."""
    baseline = _write_baseline(
        tmp_path / "proof-of-block.json",
        [
            _guard("hard-floor", fault=SILENT),
            _guard("plan-gate", fault=SILENT),
        ],
    )
    current = [
        _guard("hard-floor", fault="REFUSES"),   # recovered
        _guard("plan-gate", fault=SILENT),
    ]

    newly_silent, no_longer_silent = compare_silent_set(current, baseline)

    assert newly_silent == set()
    assert no_longer_silent == {"hard-floor"}


def test_compare_silent_set_is_a_set_not_a_count(tmp_path: Path) -> None:
    """One guard going silent while another is fixed nets out to an unchanged
    COUNT. Membership must be compared as a set or the swap is invisible."""
    baseline = _write_baseline(
        tmp_path / "proof-of-block.json",
        [_guard("a", fault=SILENT), _guard("b", fault="REFUSES")],
    )
    current = [_guard("a", fault="REFUSES"), _guard("b", fault=SILENT)]

    newly_silent, no_longer_silent = compare_silent_set(current, baseline)

    assert len(silent_set(current)) == 1  # count is unchanged...
    assert newly_silent == {"b"}          # ...but the set difference is not
    assert no_longer_silent == {"a"}


def test_compare_silent_set_raises_on_a_baseline_with_no_fault_data(
    tmp_path: Path,
) -> None:
    """The trap: a --no-fault baseline has an empty SILENT set for a trivial
    reason. Comparing against it would report "no new silent guards" and pass
    vacuously. It must raise instead.

    This is the exact shape of the committed baseline before Issue #1586, which
    carried a 'fault' key on 0 of 7 entries.
    """
    baseline = _write_baseline(
        tmp_path / "proof-of-block.json",
        [_guard("a"), _guard("b")],  # no fault key -- recorded with --no-fault
    )

    with pytest.raises(ValueError, match="no fault data"):
        compare_silent_set([_guard("a", fault=SILENT)], baseline)


def test_compare_silent_set_raises_on_empty_results(tmp_path: Path) -> None:
    baseline = _write_baseline(tmp_path / "proof-of-block.json", [])
    with pytest.raises(ValueError, match="no results"):
        compare_silent_set([_guard("a", fault=SILENT)], baseline)


def test_compare_silent_set_raises_on_missing_baseline(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="baseline not found"):
        compare_silent_set([_guard("a", fault=SILENT)],
                           tmp_path / "nope" / "proof-of-block.json")


def test_compare_silent_set_raises_on_corrupt_baseline(tmp_path: Path) -> None:
    bad = tmp_path / "proof-of-block.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        compare_silent_set([_guard("a", fault=SILENT)], bad)


# ---------------------------------------------------------------------------
# 6. the activity row must be FINDABLE
# ---------------------------------------------------------------------------

def test_activity_row_carries_the_type_marker(tmp_path: Path) -> None:
    """The sink carries 6,472-23,997 rows/day and its readers are
    pipeline-intent-shaped. An unmarked row is unfindable, which is the same
    defect as never writing it."""
    results = [_guard("a"), _guard("b", fault=SILENT)]
    written = log_activity_row(tmp_path, results, exit_code=0)

    assert written is not None
    assert written.parent == tmp_path / ".claude" / "logs" / "activity"

    rows = [json.loads(line) for line in written.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["type"] == "proof_of_block"
    assert row["exit_code"] == 0
    assert row["proven"] == 2
    assert row["total"] == 2
    assert row["verdicts"] == {"a": "PROVEN", "b": "PROVEN"}
    assert row["fault_arm"] is True
    assert row["silent"] == ["b"]


def test_activity_row_distinguishes_not_measured_from_none_found(
    tmp_path: Path,
) -> None:
    """``--no-fault`` (what /health-check uses) leaves the SILENT set empty for
    a TRIVIAL reason. Emitting ``"silent": []`` would tell the improvement loop
    "no guards fail open silently" when nothing was classified at all.

    A probe that returns zero is not evidence of zero, so the row must carry
    null plus ``fault_arm: false``.
    """
    no_fault_results = [_guard("a"), _guard("b")]  # no 'fault' key
    written = log_activity_row(tmp_path, no_fault_results, exit_code=0)
    assert written is not None
    row = json.loads(written.read_text().splitlines()[0])

    assert row["fault_arm"] is False
    assert row["silent"] is None, (
        "an empty list here reads as 'measured, none found' -- the vacuous "
        "empty set this harness exists to detect"
    )

    # Negative control, DIFFERENT shape: with the fault arm on and genuinely no
    # silent guards, the row must say so with an empty list, not null.
    measured = [_guard("a", fault="REFUSES"), _guard("b", fault="REFUSES")]
    written2 = log_activity_row(tmp_path, measured, exit_code=0)
    assert written2 is not None
    row2 = json.loads(written2.read_text().splitlines()[1])
    assert row2["fault_arm"] is True
    assert row2["silent"] == []


def test_activity_row_appends_rather_than_truncates(tmp_path: Path) -> None:
    log_activity_row(tmp_path, [_guard("a")], exit_code=0)
    written = log_activity_row(tmp_path, [_guard("a")], exit_code=1)
    assert written is not None
    assert len(written.read_text().splitlines()) == 2


def test_activity_row_is_findable_by_a_type_filter(tmp_path: Path) -> None:
    """Positive AND negative control for the reader's filter: the harness row
    must be selected and an ordinary hook row must not."""
    log_dir = tmp_path / ".claude" / "logs" / "activity"
    log_dir.mkdir(parents=True)
    day_file = sorted(log_dir.glob("*.jsonl"))
    assert not day_file  # nothing yet

    written = log_activity_row(tmp_path, [_guard("a")], exit_code=0)
    assert written is not None
    # An ordinary hook row, shaped like the 7,060 real rows observed on
    # 2026-08-21: no 'type' field at all.
    with written.open("a") as fh:
        fh.write(json.dumps({"timestamp": "t", "hook": "PreToolUse",
                             "decision": "allow", "session_id": "x"}) + "\n")

    rows = [json.loads(line) for line in written.read_text().splitlines()]
    selected = [r for r in rows if r.get("type") == "proof_of_block"]
    assert len(selected) == 1, "positive control: the harness row is selected"
    assert len(rows) == 2, "negative control: the hook row is present..."
    assert selected[0]["hook"] == "proof_of_block", "...and not selected"


# ---------------------------------------------------------------------------
# 7. no control arm removed or weakened (AC12)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "marker,why",
    [
        ("def _real_repo", "guards scoped to the canonical source need the real repo"),
        ("if root == REPO:", "the corruption refusal must still fire"),
        ('env["PIPELINE_STATE_FILE"]', "the sentinel redirect (Defect 1)"),
        ("def _preserved_plan_exit_marker", "the marker snapshot/restore (Defect 1)"),
        ("def _first_real_repo_guard", "fixture selection by identity (Defect 2)"),
        ('out["verdict"] = "UNVERIFIED"', "a missing hook is a finding, not a skip"),
        ("def verify_injection_instrument", "the instrument's matched pair"),
        ("def verify_classifier", "the classifier's three synthetic cases"),
        ("def classify_outcome", "REFUSES / LOUD / SILENT classification"),
        ('out["negative_control"]', "the instrument's negative control"),
        ('out["positive_control"]', "the instrument's positive control"),
        ("trace_probe", "the log-trace probe"),
        ('"ok": dec in BLOCKED', "the positive arm: must refuse"),
        ('"ok": dec not in BLOCKED', "the negative arm: must permit"),
    ],
)
def test_control_arms_survive_the_port(marker: str, why: str) -> None:
    """A portable harness that lost a control arm would be WORSE than the
    original, because it would report PROVEN without being able to fail."""
    source = SCRIPT_PATH.read_text()
    assert marker in source, f"control arm removed: {why}"


# ---------------------------------------------------------------------------
# 8. the probe must not MUTATE the repository it measures
# ---------------------------------------------------------------------------
# Deciding is not free. PreToolUse returns a decision without performing the
# tool call, but the hook reads and PRUNES its own state on the way there, and
# two of those pruning arms unlink real files under the driven cwd -- which is
# the user's own repository for the four ``_real_repo`` guards. Since #1586 this
# script ships to consumer repos and is invoked by ``/health-check``, so a
# developer could degrade their own enforcement mid-``/implement``.


def _fixture_with_sentinel(root: Path, stored_session_id: str) -> tuple[Path, Path]:
    """Build an adev fixture carrying a pipeline sentinel at the DEFAULT path.

    The default path is what matters: ``get_legacy_sentinel_path()`` resolves
    ``<repo_root>/.claude/local/implement_pipeline_state.json`` from the driven
    cwd, so planting it anywhere else would not reproduce the hazard.

    Args:
        root: Throwaway directory.
        stored_session_id: Value written into the sentinel's ``session_id``.

    Returns:
        ``(root, sentinel_path)``.
    """
    _adev_repo(root)
    sentinel = root / ".claude" / "local" / "implement_pipeline_state.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(
        json.dumps(
            {
                "session_id": stored_session_id,
                "issue_number": 1586,
                "mode": "full",
                "current_step": 5,
            }
        )
    )
    return root, sentinel


@pytest.mark.slow
def test_regression_issue_1586_probe_does_not_delete_real_pipeline_state(
    tmp_path: Path,
) -> None:
    """A sentinel owned by ANOTHER session must survive a probe run.

    ``drive_raw`` drives ``session_id: "proof-of-block"``. The hook does not
    treat that as a label -- ``_is_stale_session()`` reads it as an OWNERSHIP
    CLAIM and calls ``state_path.unlink(missing_ok=True)`` whenever the stored
    id differs. Every run of this harness therefore deleted the live sentinel of
    whatever session was in flight, reaching the exact deletion Issue #803's
    Bash guard hard-blocks without ever traversing that guard.

    This asserts the BEHAVIOUR (the file is still there), not the mechanism. A
    test asserting only "drive_raw sets PIPELINE_STATE_FILE" would pass against
    a redirect aimed at the wrong path, and would keep passing if the hook
    stopped honouring the variable -- it would test the implementation instead
    of the property that matters.
    """
    root, sentinel = _fixture_with_sentinel(tmp_path / "fixture", FOREIGN_SESSION_ID)
    before = sentinel.read_bytes()

    result = drive_raw(
        UNIFIED_PRE_TOOL,
        "Write",
        {"file_path": str(root / "src" / "a.py"), "content": "x = 1\n"},
        root,
    )

    assert sentinel.exists(), (
        "the probe DELETED a pipeline sentinel belonging to another session; "
        "PIPELINE_STATE_FILE is not being redirected away from the real path"
    )
    assert sentinel.read_bytes() == before, "the sentinel was rewritten"
    assert result["decision"] in ("allow", "deny", "ask", "block"), (
        "the hook must still return a real decision through the redirect"
    )


@pytest.mark.slow
def test_regression_issue_1586_sentinel_deletion_probe_can_actually_fire(
    tmp_path: Path,
) -> None:
    """POSITIVE CONTROL for the test above: reinstate the bug, watch it delete.

    Without this, ``test_..._does_not_delete_real_pipeline_state`` would pass
    just as happily if the deletion branch were unreachable in a temp fixture --
    a probe that cannot fail cannot inform. Overriding ``PIPELINE_STATE_FILE``
    back to the fixture's own default path restores exactly the pre-fix
    condition, and the sentinel must then be destroyed.
    """
    root, sentinel = _fixture_with_sentinel(tmp_path / "fixture", FOREIGN_SESSION_ID)

    drive_raw(
        UNIFIED_PRE_TOOL,
        "Write",
        {"file_path": str(root / "src" / "a.py"), "content": "x = 1\n"},
        root,
        env_overrides={"PIPELINE_STATE_FILE": str(sentinel)},
    )

    assert not sentinel.exists(), (
        "the deletion branch did not fire even when aimed straight at the "
        "sentinel -- this test's observation apparatus is broken, so the "
        "survival asserted by the companion test proves nothing"
    )


@pytest.mark.slow
def test_regression_issue_1586_probe_restores_the_plan_exit_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale ``.claude/plan_mode_exit.json`` under REPO must survive a run.

    ``_read_plan_exit_marker()`` resolves the marker from ``os.getcwd()`` and
    unlinks it when it is stale-by-TTL or corrupt. Measured against the real
    repository before the fix: 5 of 8 ``_real_repo`` guard runs deleted a
    planted stale marker.

    ``REPO`` is monkeypatched onto the fixture so the real repository is never
    written to, while the code path exercised is the same one.
    """
    root = _adev_repo(tmp_path / "fixture")
    monkeypatch.setattr(proof_of_block, "REPO", root)

    marker = root / ".claude" / "plan_mode_exit.json"
    stale = json.dumps(
        {
            "timestamp": "2020-01-01T00:00:00+00:00",  # far outside the 30min TTL
            "session_id": "someone-else",
            "stage": "plan_exited",
        }
    )
    marker.write_text(stale)

    drive_raw(
        UNIFIED_PRE_TOOL,
        "Write",
        {"file_path": str(root / "src" / "a.py"), "content": "x = 1\n"},
        root,
    )

    assert marker.exists(), (
        "the probe consumed real plan-mode state; the snapshot/restore in "
        "_preserved_plan_exit_marker did not engage"
    )
    assert marker.read_text() == stale, "the marker was restored with wrong content"


@pytest.mark.slow
def test_regression_issue_1586_plan_marker_deletion_probe_can_actually_fire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POSITIVE CONTROL, different shape: with REPO pointed ELSEWHERE, the
    preservation must not engage and the hook must eat the stale marker.

    This is what distinguishes "we restore it" from "nothing ever deletes it".
    """
    root = _adev_repo(tmp_path / "fixture")
    monkeypatch.setattr(proof_of_block, "REPO", tmp_path / "somewhere-else")

    marker = root / ".claude" / "plan_mode_exit.json"
    marker.write_text(
        json.dumps(
            {
                "timestamp": "2020-01-01T00:00:00+00:00",
                "session_id": "someone-else",
                "stage": "plan_exited",
            }
        )
    )

    drive_raw(
        UNIFIED_PRE_TOOL,
        "Write",
        {"file_path": str(root / "src" / "a.py"), "content": "x = 1\n"},
        root,
    )

    assert not marker.exists(), (
        "a stale marker survived a run that was NOT protected -- the probe "
        "cannot observe the deletion it claims to prevent"
    )


def test_drive_raw_payload_uses_the_session_tag_the_log_probe_filters_on() -> None:
    """The tag is load-bearing in two places and must not drift.

    ``_log_rows()`` attributes rows to this harness by filtering on
    ``SESSION_TAG``; the payload must carry that same value or the trace probe
    silently counts nothing.
    """
    source = SCRIPT_PATH.read_text()
    assert '"session_id": SESSION_TAG,' in source, (
        "the drive payload must reference SESSION_TAG rather than repeating the "
        "literal, so the tag and the log filter cannot diverge"
    )
    assert SESSION_TAG == "proof-of-block"


# ---------------------------------------------------------------------------
# 9. fixtures must refuse the real repo (Defect 2)
# ---------------------------------------------------------------------------
# ``_adev_repo`` runs ``git init`` and overwrites
# ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` with a 31-byte
# stub. The real file is 7kB and is the marker CLAUDE.md documents as the
# detector for self-maintenance mode. Before the fix the only thing standing
# between that and destruction was ``GUARDS[0]``'s fixture happening to be
# ``_real_repo``, which ignores its argument.


def test_adev_repo_refuses_the_real_repo() -> None:
    """The REFUSING arm. Covers the CLASS: the refusal lives in the fixture, so
    it holds for every caller, present and future -- not at one call site."""
    with pytest.raises(RuntimeError, match="refusing to build"):
        _adev_repo(REPO)


def test_plan_exited_refuses_the_real_repo() -> None:
    """A DIFFERENT caller of the same fixture must inherit the refusal.

    ``_plan_exited`` delegates to ``_adev_repo`` and then writes live plan-exit
    state. A guard placed at the ``_adev_repo`` call site inside
    ``verify_injection_instrument`` would not have covered this path at all --
    which is the difference between fixing the class and fixing the instance.
    """
    with pytest.raises(RuntimeError, match="refusing to build"):
        _plan_exited(REPO)


def test_adev_repo_still_builds_a_legitimate_temp_fixture(tmp_path: Path) -> None:
    """The PERMITTING arm. A guard that refuses everything is not a fix."""
    root = _adev_repo(tmp_path / "fixture")

    assert root == tmp_path / "fixture"
    assert (root / ".git").exists(), "git init must still run"
    manifest = root / "plugins" / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
    assert "autonomous-dev" in manifest.read_text(), (
        "repo_detector keys off marketplace.json CONTENT, not its existence"
    )
    assert (root / ".claude").is_dir()
    assert (root / "docs").is_dir()


def test_plan_exited_still_builds_a_legitimate_temp_fixture(tmp_path: Path) -> None:
    root = _plan_exited(tmp_path / "fixture")
    marker = json.loads((root / ".claude" / "plan_mode_exit.json").read_text())
    assert marker["stage"] == "plan_exited"


def test_real_repo_fixture_still_returns_the_real_repo(tmp_path: Path) -> None:
    """``_real_repo`` must keep ignoring its argument.

    The four guards using it scope their enforcement to the canonical source; a
    synthetic temp repo makes those guards correctly decline to fire, which the
    harness would read as a false FAILS-OPEN.
    """
    assert _real_repo(tmp_path) == REPO


def test_injection_instrument_selects_its_guard_by_fixture_not_by_position() -> None:
    """Reordering GUARDS must not change which fixture gets the real repo."""
    chosen = _first_real_repo_guard()
    assert chosen["fixture"] is _real_repo
    assert chosen in proof_of_block.GUARDS


def test_injection_instrument_guard_selection_survives_a_reorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The REFUSING arm of the positional coupling: put a temp-dir fixture
    first and the selector must still pick the ``_real_repo`` one.

    Under ``GUARDS[0]`` this returned the ``_plan_exited`` guard, whose fixture
    would then have been handed ``REPO``.
    """
    real = _first_real_repo_guard()
    decoy = {"guard": "decoy", "issue": "#0", "hook": "h.py",
             "fixture": _plan_exited, "positive": {}, "negative": {}}
    monkeypatch.setattr(proof_of_block, "GUARDS", [decoy, real])

    assert _first_real_repo_guard() is real
    assert proof_of_block.GUARDS[0] is decoy, "the decoy really was first"


def test_injection_instrument_refuses_when_no_real_repo_guard_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A roster with no ``_real_repo`` guard is an instrument fault, not a
    silent substitution."""
    decoy = {"guard": "decoy", "issue": "#0", "hook": "h.py",
             "fixture": _plan_exited, "positive": {}, "negative": {}}
    monkeypatch.setattr(proof_of_block, "GUARDS", [decoy])

    with pytest.raises(RuntimeError, match="no guard uses the _real_repo fixture"):
        _first_real_repo_guard()


# ---------------------------------------------------------------------------
# 10. a broken INSTRUMENT is not a guard FINDING (Defect 3)
# ---------------------------------------------------------------------------
# ``main()`` handles ``(FileNotFoundError, ValueError)`` and returns
# EXIT_UNRESOLVABLE (2) -- "the harness could not run". Anything else escapes as
# a traceback and exits 1 -- "the harness ran and found a guard problem" -- and
# an operator then goes hunting for a broken guard that does not exist. That
# conflation is the precise thing this harness exists to prevent.

MALFORMED_BASELINES = [
    pytest.param("5", "not a JSON object", id="json-scalar-int"),
    pytest.param('"hello"', "not a JSON object", id="json-scalar-str"),
    pytest.param("[]", "not a JSON object", id="json-list"),
    pytest.param('[{"guard": "a"}]', "not a JSON object", id="json-list-of-objects"),
    pytest.param('{"results": 5}', "not an array", id="results-scalar"),
    pytest.param('{"results": [1, 2]}', "non-object result entries",
                 id="results-of-scalars"),
    pytest.param('{"results": [{"guard": "a", "fault": {}}, "x"]}',
                 "non-object result entries", id="results-mixed"),
]


@pytest.mark.parametrize("payload,expected", MALFORMED_BASELINES)
def test_compare_silent_set_reports_malformed_baseline_as_instrument_failure(
    tmp_path: Path, payload: str, expected: str
) -> None:
    """Each shape below raised AttributeError or TypeError before the fix.

    Measured against the live function: ``5`` -> ``AttributeError: 'int' object
    has no attribute 'get'``; ``[]`` -> the same for ``'list'``;
    ``{"results": [1, 2]}`` -> ``TypeError: argument of type 'int' is not a
    container``. All three escaped ``main()``'s handler and exited 1.
    """
    bad = tmp_path / "proof-of-block.json"
    bad.write_text(payload)

    with pytest.raises(ValueError, match=expected):
        compare_silent_set([_guard("a", fault=SILENT)], bad)


@pytest.mark.parametrize("payload,_expected", MALFORMED_BASELINES)
def test_compare_silent_set_malformed_baseline_is_caught_by_mains_handler(
    tmp_path: Path, payload: str, _expected: str
) -> None:
    """The raised type must be one ``main()`` actually catches.

    Asserting ``ValueError`` alone would still pass if the message shape were
    right but the exception escaped a different way, so this pins the exact
    tuple in ``main()`` -- the property that decides exit 2 versus exit 1.
    """
    bad = tmp_path / "proof-of-block.json"
    bad.write_text(payload)

    try:
        compare_silent_set([_guard("a", fault=SILENT)], bad)
    except (FileNotFoundError, ValueError):
        pass  # main()'s handler catches this -> EXIT_UNRESOLVABLE
    except BaseException as exc:  # noqa: BLE001 - the whole point of the test
        pytest.fail(
            f"{type(exc).__name__} escapes main()'s (FileNotFoundError, "
            f"ValueError) handler and exits 1, which means 'a guard is broken'"
        )
    else:
        pytest.fail("a malformed baseline must not be accepted silently")


def test_compare_silent_set_still_accepts_a_well_formed_baseline(
    tmp_path: Path,
) -> None:
    """The PERMITTING arm. The shape checks must not refuse valid baselines.

    A well-formed baseline with a KNOWN silent set must still produce the
    correct set difference in both directions.
    """
    baseline = _write_baseline(
        tmp_path / "proof-of-block.json",
        [_guard("a", fault=SILENT), _guard("b", fault="REFUSES")],
    )

    newly_silent, no_longer_silent = compare_silent_set(
        [_guard("a", fault="REFUSES"), _guard("b", fault=SILENT)], baseline
    )

    assert newly_silent == {"b"}
    assert no_longer_silent == {"a"}, (
        "membership must be compared as a SET -- these two net out to an "
        "unchanged COUNT, which is the regression the ratchet exists to catch"
    )
