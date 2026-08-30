"""Validator-artifact receipt cross-check in the agent-completeness gate.

``implement.md`` instructs the coordinator to persist reviewer and
security-auditor output verbatim to
``.claude/logs/activity/validators/<run_id>/<agent>.txt``. That instruction is
prose, and prose does not refuse: on 2026-08-29 the write was skipped entirely
and a reviewer REQUEST_CHANGES finding that had driven a full remediation cycle
existed only in narration, unverifiable by the CIA. Two empty ``validators/``
directories in this repo's own activity log are live instances of the class.

These tests pin :func:`pipeline_completion_state._missing_validator_artifacts`,
which makes a single-issue run that CLAIMS a validator completion but left no
artifact on disk fail the gate.

Both arms are exercised deliberately. Refusal alone would be satisfied by a
check that can only ever refuse; the permitting arm (tests 2, 4, 6-11, 13b) is
what proves the check discriminates. Test 4 in particular is a negative control
against a byte-threshold regression: it feeds the real 138-byte single-line
APPROVE verdict from the corpus, which any ``>=200 bytes`` rule would reject.

Tracking issue: to be filed post-merge (no issue existed when this was written).
"""

import os
import re
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import pipeline_completion_state as P  # noqa: E402
from pipeline_completion_state import (  # noqa: E402
    _missing_validator_artifacts,
    _state_file_path,
    record_agent_completion,
    record_run_start,
    verify_pipeline_agent_completions,
)

# The exact 138-byte, single-line reviewer verdict from this repo's real
# corpus (``validators/issue-1193-20260616-025336/reviewer.txt``). It is the
# SMALLEST genuine artifact on disk and exists here to break any future
# byte-count or line-count threshold.
REAL_138_BYTE_VERDICT = (
    "REVIEWER-VERDICT: APPROVE — checklist all PASS. canonicalize-then-contain "
    "pattern correct. 19 tests pass. No BLOCKING/WARNING findings.\n"
)

# Agents required by each mode, bound here so a change to the required set
# surfaces as a readable failure. "full" is the only common mode requiring
# BOTH validators; "fix" requires reviewer only; "light" requires neither.
FULL_MODE_VALIDATORS = ("reviewer", "security-auditor")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def sid() -> str:
    """Per-test unique session id.

    ``/tmp`` state is process-global and is NOT cleared between pytest
    invocations, so a fixed literal would let a leaked file from an earlier
    run poison this one.
    """
    return f"test-vart-{os.getpid()}-{time.time_ns()}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def run_id() -> str:
    """A run id that satisfies ``_RUN_ID_RE`` by construction."""
    return f"run-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def isolate_gate_environment(monkeypatch, tmp_path):
    """Remove ambient influences that would make these assertions unfalsifiable.

    1. ``SKIP_AGENT_COMPLETENESS_GATE`` — makes the gate return
       ``(True, set(), set())`` unconditionally, so a refusal test could never
       observe a refusal.
    2. ``/tmp/skip_agent_completeness_gate`` — the file-based one-shot bypass.
       Re-pointed at a nonexistent path under ``tmp_path`` rather than deleted,
       because ``_check_file_bypass`` CONSUMES the real file and deleting a
       maintainer's live bypass from a test would be a destructive side effect.
    3. The process CWD — ``_find_activity_log_dir`` walks up from it and would
       otherwise find this repo's own ``.claude/logs/activity/``, silently
       coupling every assertion to real activity-log contents.
    """
    monkeypatch.delenv("SKIP_AGENT_COMPLETENESS_GATE", raising=False)
    monkeypatch.delenv("SKIP_PYTEST_GATE", raising=False)
    monkeypatch.setattr(P, "SKIP_GATE_FILE", tmp_path / "no-such-bypass-file")
    monkeypatch.setattr(P, "STALE_UNKNOWN_TTL_SECONDS", 0)
    (tmp_path / ".claude" / "logs" / "activity").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    yield


@pytest.fixture(autouse=True)
def cleanup_state(sid):
    """Remove this test's state and lock files, whatever the outcome."""
    try:
        yield
    finally:
        path = _state_file_path(sid)
        try:
            path.unlink(missing_ok=True)
            path.with_suffix(".lock").unlink(missing_ok=True)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _activity_dir(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "logs" / "activity"


def _write_artifact(tmp_path: Path, run: str, agent: str, text: str) -> Path:
    """Write a validator artifact where implement.md's mkdir -p would put it."""
    d = _activity_dir(tmp_path) / "validators" / run
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{agent}.txt"
    p.write_text(text, encoding="utf-8")
    return p


def _record_full_pipeline(session_id: str, run: str) -> None:
    """Record every agent "full" mode requires, using the PRODUCTION writer
    shape (no ``run_id=`` kwarg — zero production call sites pass one)."""
    assert record_run_start(session_id, run) is True
    for agent in (
        "researcher",
        "researcher-local",
        "planner",
        "plan-critic",
        "implementer",
        "reviewer",
        "security-auditor",
        "doc-master",
    ):
        record_agent_completion(session_id, agent)
    P.record_pytest_gate_passed(session_id)


# --------------------------------------------------------------------------- #
# 1-5: the core refuse/permit discrimination, through the real gate
# --------------------------------------------------------------------------- #


def test_1_both_artifacts_absent_blocks(sid, run_id, tmp_path) -> None:
    """Both validators credited, neither artifact on disk → gate refuses."""
    _record_full_pipeline(sid, run_id)

    passed, completed, missing = verify_pipeline_agent_completions(
        sid, "full", issue_number=0
    )

    assert passed is False, (
        "gate passed a run that recorded reviewer + security-auditor "
        f"completions but wrote no artifacts; missing={sorted(missing)}"
    )
    sentinel_agents = {
        s.split("-artifact:", 1)[0] for s in missing if "-artifact:" in s
    }
    assert sentinel_agents == set(FULL_MODE_VALIDATORS), (
        f"expected a sentinel for each validator, got {sorted(missing)}"
    )


def test_2_both_artifacts_present_passes(sid, run_id, tmp_path) -> None:
    """PERMITTING ARM: artifacts present and non-empty → gate passes clean."""
    _record_full_pipeline(sid, run_id)
    for agent in FULL_MODE_VALIDATORS:
        _write_artifact(tmp_path, run_id, agent, f"{agent} verdict: APPROVE\n")

    passed, completed, missing = verify_pipeline_agent_completions(
        sid, "full", issue_number=0
    )

    assert passed is True, f"artifacts were written but gate refused: {sorted(missing)}"
    assert missing == set()


def test_3_one_artifact_absent_yields_exactly_one_sentinel(
    sid, run_id, tmp_path
) -> None:
    """Only the validator whose artifact is missing is reported."""
    _record_full_pipeline(sid, run_id)
    _write_artifact(tmp_path, run_id, "reviewer", "REVIEWER-VERDICT: APPROVE\n")

    passed, _, missing = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert passed is False
    sentinels = [s for s in missing if "-artifact:" in s]
    assert len(sentinels) == 1, f"expected exactly one sentinel, got {sentinels}"
    assert sentinels[0].startswith("security-auditor-artifact:"), sentinels[0]


def test_4_real_138_byte_verdict_passes_no_byte_threshold(
    sid, run_id, tmp_path
) -> None:
    """NEGATIVE CONTROL against a byte-threshold regression.

    This is the verbatim smallest genuine artifact in the real corpus: 138
    bytes, one line. An earlier draft's ``>=200 bytes AND >=2 lines`` rule
    misclassified 6 of 19 genuine artifacts, this one among them. If someone
    reintroduces a threshold, this test refuses it.
    """
    # Byte-identical to validators/issue-1193-20260616-025336/reviewer.txt,
    # verified against the real file: 138 bytes including the trailing newline,
    # a single line of content.
    assert len(REAL_138_BYTE_VERDICT.encode("utf-8")) == 138
    assert REAL_138_BYTE_VERDICT.rstrip("\n").count("\n") == 0

    _record_full_pipeline(sid, run_id)
    _write_artifact(tmp_path, run_id, "reviewer", REAL_138_BYTE_VERDICT)
    _write_artifact(tmp_path, run_id, "security-auditor", REAL_138_BYTE_VERDICT)

    passed, _, missing = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert passed is True, (
        "a real 138-byte single-line verdict was rejected — a byte or line "
        f"threshold has been reintroduced. missing={sorted(missing)}"
    )


def test_5_zero_byte_artifact_is_treated_as_absent(sid, run_id, tmp_path) -> None:
    """Emptiness is judged by zero bytes only — a 0-byte file does not count."""
    _record_full_pipeline(sid, run_id)
    _write_artifact(tmp_path, run_id, "reviewer", "")
    _write_artifact(tmp_path, run_id, "security-auditor", "ok\n")

    passed, _, missing = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert passed is False
    sentinels = [s for s in missing if "-artifact:" in s]
    assert len(sentinels) == 1 and sentinels[0].startswith("reviewer-artifact:"), (
        f"zero-byte reviewer.txt must be reported absent-or-empty, got {sentinels}"
    )


# --------------------------------------------------------------------------- #
# 6-10: INV-7 — every indeterminate input contributes nothing
# --------------------------------------------------------------------------- #


def test_6_batch_scope_contributes_nothing(sid, run_id, tmp_path) -> None:
    """``issue_number != 0``: the artifact dir name is not derivable, so the
    check must abstain rather than block a batch run that DID write its
    artifacts."""
    out = _missing_validator_artifacts(
        run_id,
        completed={"reviewer", "security-auditor"},
        required={"reviewer", "security-auditor"},
        issue_number=5,
        activity_dir=_activity_dir(tmp_path),
    )
    assert out == frozenset()


def test_7_no_current_run_id_contributes_nothing(tmp_path) -> None:
    """No run identity recorded → indeterminate, not absent."""
    for falsy in (None, ""):
        out = _missing_validator_artifacts(
            falsy,
            completed={"reviewer", "security-auditor"},
            required={"reviewer", "security-auditor"},
            issue_number=0,
            activity_dir=_activity_dir(tmp_path),
        )
        assert out == frozenset(), f"falsy run id {falsy!r} must contribute nothing"


def test_8_traversal_run_id_abstains_and_stats_nothing(tmp_path, monkeypatch) -> None:
    """A ``current_run_id`` failing ``_RUN_ID_RE`` abstains AND probes no path.

    The zero-probe observation is only meaningful with a POSITIVE CONTROL: the
    same recorder, given a valid run id, must record probes. Without it, a
    recorder that never fires would produce the same "zero" for a broken
    instrument as for a working guard.
    """
    probed: list[str] = []
    real_is_file = Path.is_file

    def recording_is_file(self):
        probed.append(str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", recording_is_file)

    # Positive control: a VALID run id must produce probes.
    out_valid = _missing_validator_artifacts(
        "valid-run-id",
        completed={"reviewer"},
        required={"reviewer"},
        issue_number=0,
        activity_dir=_activity_dir(tmp_path),
    )
    assert probed, "instrument is broken: valid run id produced no probe at all"
    assert out_valid, "valid run id with no artifact on disk should emit a sentinel"

    # Now the actual assertion.
    probed.clear()
    out = _missing_validator_artifacts(
        "../../etc",
        completed={"reviewer"},
        required={"reviewer"},
        issue_number=0,
        activity_dir=_activity_dir(tmp_path),
    )
    assert out == frozenset(), "traversal run id must contribute nothing"
    assert probed == [], f"traversal run id must not be stat'd at all, probed={probed}"


def test_9_no_activity_dir_contributes_nothing(run_id) -> None:
    """``_find_activity_log_dir()`` returning None → indeterminate."""
    out = _missing_validator_artifacts(
        run_id,
        completed={"reviewer", "security-auditor"},
        required={"reviewer", "security-auditor"},
        issue_number=0,
        activity_dir=None,
    )
    # With activity_dir=None the helper resolves via _find_activity_log_dir();
    # the autouse fixture chdir'd into a tmp repo skeleton that HAS one, so
    # this exercises the resolve path. The pure "no ancestor" arm is test 13b.
    assert isinstance(out, frozenset)


def test_10_agent_completed_but_not_required_yields_no_sentinel(
    run_id, tmp_path
) -> None:
    """Light mode requires neither validator. A reviewer completion recorded
    anyway must not manufacture a requirement that the mode never had."""
    out = _missing_validator_artifacts(
        run_id,
        completed={"reviewer", "security-auditor", "implementer"},
        required={"implementer", "doc-master", "pytest-gate"},
        issue_number=0,
        activity_dir=_activity_dir(tmp_path),
    )
    assert out == frozenset()


def test_10b_helper_never_raises_on_oserror(run_id, tmp_path, monkeypatch) -> None:
    """AC4: any OSError is indeterminate, and the helper never propagates it."""

    def exploding_stat(self, *a, **kw):
        raise OSError("simulated stat failure")

    _write_artifact(tmp_path, run_id, "reviewer", "content\n")
    monkeypatch.setattr(Path, "stat", exploding_stat)

    out = _missing_validator_artifacts(
        run_id,
        completed={"reviewer"},
        required={"reviewer"},
        issue_number=0,
        activity_dir=_activity_dir(tmp_path),
    )
    assert out == frozenset()


# --------------------------------------------------------------------------- #
# 11: bypasses short-circuit BEFORE any artifact probe
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "Yes"])
def test_11_env_bypass_short_circuits_before_probe(
    sid, run_id, monkeypatch, value
) -> None:
    """AC5: env bypass returns clean without the artifact check ever running."""
    calls: list[tuple] = []

    def recording_helper(*a, **kw):
        calls.append((a, kw))
        return frozenset()

    monkeypatch.setattr(P, "_missing_validator_artifacts", recording_helper)
    _record_full_pipeline(sid, run_id)

    # Positive control: WITHOUT the bypass the helper is reached.
    verify_pipeline_agent_completions(sid, "full", issue_number=0)
    assert calls, "instrument is broken: helper not reached even without bypass"
    calls.clear()

    monkeypatch.setenv("SKIP_AGENT_COMPLETENESS_GATE", value)
    result = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert result == (True, set(), set())
    assert calls == [], "bypass must short-circuit before any artifact probe"


def test_11b_file_bypass_short_circuits_before_probe(
    sid, run_id, tmp_path, monkeypatch
) -> None:
    """AC5: the /tmp token form also short-circuits before the artifact check.

    The fixture repointed ``SKIP_GATE_FILE`` under ``tmp_path``; creating THAT
    file exercises the bypass without touching a maintainer's live token.
    """
    calls: list[tuple] = []
    monkeypatch.setattr(
        P, "_missing_validator_artifacts", lambda *a, **kw: calls.append(1) or frozenset()
    )
    _record_full_pipeline(sid, run_id)

    P.SKIP_GATE_FILE.write_text("", encoding="utf-8")
    result = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert result == (True, set(), set())
    assert calls == [], "file bypass must short-circuit before any artifact probe"


# --------------------------------------------------------------------------- #
# 12: rendering through the existing call sites (no call site is edited)
# --------------------------------------------------------------------------- #


def test_12_sentinel_renders_intact_and_contains_no_comma(
    sid, run_id, tmp_path
) -> None:
    """AC6: sentinels survive ``", ".join(sorted(missing))`` — the exact shape
    used at both ``unified_pre_tool.py`` call sites — without being split."""
    _record_full_pipeline(sid, run_id)

    _, _, missing = verify_pipeline_agent_completions(sid, "full", issue_number=0)
    sentinels = [s for s in missing if "-artifact:" in s]
    assert sentinels, "precondition: the refusing arm must have produced sentinels"

    for s in sentinels:
        assert "," not in s, f"sentinel contains a comma and will be split: {s!r}"

    rendered = ", ".join(sorted(missing))
    for s in sentinels:
        assert s in rendered, f"sentinel mangled by join: {s!r} not in {rendered!r}"
    assert len(rendered.split(", ")) == len(missing)


# --------------------------------------------------------------------------- #
# 13: the real CWD walk-up, unmonkeypatched — both arms
# --------------------------------------------------------------------------- #


def test_13a_real_cwd_walkup_finds_artifact_written_relatively(
    sid, run_id, tmp_path
) -> None:
    """The §3.1 CWD assumption, exercised end to end.

    The artifact is written through the LITERAL relative path shape that
    implement.md's ``mkdir -p`` uses, and the gate is called with NO
    activity-dir monkeypatching — so ``_find_activity_log_dir`` must walk up
    from the real process CWD and land on the same tree.
    """
    _record_full_pipeline(sid, run_id)
    for agent in FULL_MODE_VALIDATORS:
        rel = Path(f".claude/logs/activity/validators/{run_id}/{agent}.txt")
        rel.parent.mkdir(parents=True, exist_ok=True)
        rel.write_text(f"{agent} verdict\n", encoding="utf-8")

    passed, _, missing = verify_pipeline_agent_completions(sid, "full", issue_number=0)

    assert passed is True, (
        "artifacts written via the relative shape implement.md uses were not "
        f"found by the CWD walk-up; missing={sorted(missing)}"
    )


def test_13b_unresolvable_activity_dir_makes_check_abstain(
    sid, run_id, tmp_path, monkeypatch
) -> None:
    """NEGATIVE CONTROL for 13a: when the resolver cannot find an activity
    tree, the helper abstains rather than blocking.

    The resolver is stubbed rather than driven by a real ``.claude``-free
    directory, because on macOS no such directory is reachable from a pytest
    tmp dir: this machine has a stray ``.claude/logs/activity`` at
    ``$TMPDIR``'s parent (accumulating real activity logs since 2026-06-14),
    so the walk-up ALWAYS finds one. Attempting the filesystem-driven version
    produced a control that could not control anything.

    Both arms are asserted here so the stub cannot silently become inert.
    """
    calls: list = []

    # Arm 1 — resolver succeeds: the helper must produce a sentinel.
    monkeypatch.setattr(
        P,
        "_find_activity_log_dir",
        lambda *a, **kw: calls.append("hit") or _activity_dir(tmp_path),
    )
    out_found = _missing_validator_artifacts(
        run_id,
        completed={"reviewer"},
        required={"reviewer"},
        issue_number=0,
    )
    assert calls, "instrument broken: helper never consulted the resolver"
    assert out_found, "positive control: a resolved dir with no artifact must refuse"

    # Arm 2 — resolver returns None: the helper must abstain.
    monkeypatch.setattr(P, "_find_activity_log_dir", lambda *a, **kw: None)
    out_none = _missing_validator_artifacts(
        run_id,
        completed={"reviewer", "security-auditor"},
        required={"reviewer", "security-auditor"},
        issue_number=0,
    )
    assert out_none == frozenset()


# --------------------------------------------------------------------------- #
# 14: pins the batch-divergence proof that justifies the issue-0 scoping
# --------------------------------------------------------------------------- #


def test_14_batch_run_id_shapes_diverge(tmp_path) -> None:
    """The two ``ISSUE_RUN_ID`` bindings in implement-batch.md are different
    shapes, which is WHY this check is scoped to single-issue runs.

    The shape that NAMES the validators directory is too long to be a valid
    run id; the shape that reaches ``record_run_start`` (and so becomes
    ``current_run_id``) is valid. A batch-scoped check would therefore look in
    a directory that never exists and block runs that wrote their artifacts.
    """
    batch_md = (
        REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
    ).read_text(encoding="utf-8")

    assert 'ISSUE_RUN_ID="${BATCH_ID}-issue${ISSUE_NUMBER}"' in batch_md, (
        "the directory-naming binding is gone — re-derive the scoping argument"
    )
    assert 'ISSUE_RUN_ID="issue-${ISSUE_NUMBER}-$(date' in batch_md, (
        "the record_run_start binding is gone — re-derive the scoping argument"
    )

    # A realized instance of the directory-naming shape, taken from this
    # repo's own activity log.
    dir_shape = (
        "batch-issues-1200-1201-1202-plus2-noworktree-20260611-073327-issue1200"
    )
    assert len(dir_shape) > 64
    assert not P._RUN_ID_RE.match(dir_shape), (
        "the batch directory name became a valid run id — the divergence "
        "argument for issue-0 scoping no longer holds and must be revisited"
    )

    # The shape that actually becomes current_run_id IS valid.
    stamped_shape = "issue-1193-20260616-025336"
    assert P._RUN_ID_RE.match(stamped_shape)

    # Therefore: a batch run, scoped by issue key, contributes nothing.
    out = _missing_validator_artifacts(
        stamped_shape,
        completed={"reviewer", "security-auditor"},
        required={"reviewer", "security-auditor"},
        issue_number=1200,
        activity_dir=_activity_dir(tmp_path),
    )
    assert out == frozenset()
