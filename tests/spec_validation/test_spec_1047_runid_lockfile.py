"""Spec-blind validation for Issue #1047 (M0/B): run_id + lockfile.

Tests are derived ONLY from the 7 acceptance criteria and the documented
public API surface. They MUST NOT inspect implementation details.

Public API under test (in `plugins/autonomous-dev/lib/pipeline_state.py`):
    - generate_run_id() -> str  (16-char hex)
    - acquire_run_lock(run_id: str) -> Optional[int]
    - release_run_lock(fd: int) -> None
    - classify_resume_id(arg: str) -> str
    - get_lockfile_path(run_id: str) -> Path
"""
from __future__ import annotations

import multiprocessing
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import pipeline_state  # noqa: E402


# =============================================================================
# AC1: STEP 0 generates run_id and exports RUN_ID + PIPELINE_STATE_FILE
# =============================================================================


def test_ac1_implement_md_step0_generates_runid_and_exports_envvars():
    """STEP 0 of implement.md MUST generate a run_id and export both
    RUN_ID and PIPELINE_STATE_FILE for downstream consumers.

    Spec-derived: AC1 is a file-shape check. We require:
      - implement.md sets RUN_ID via secrets.token_hex(8) (16-char hex spec).
      - implement.md exports RUN_ID.
      - implement.md exports PIPELINE_STATE_FILE.
    """
    impl = (REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md").read_text()
    assert "secrets.token_hex(8)" in impl, (
        "STEP 0 must use secrets.token_hex(8) to generate the 16-char hex run_id"
    )
    assert re.search(r"^export\s+RUN_ID\b", impl, re.MULTILINE), (
        "STEP 0 must `export RUN_ID` so child processes inherit it"
    )
    assert re.search(r"^export\s+PIPELINE_STATE_FILE=", impl, re.MULTILINE), (
        "STEP 0 must `export PIPELINE_STATE_FILE=...` so hooks can find the state file"
    )


def test_ac1_generate_run_id_returns_16char_hex():
    """The public API generate_run_id() MUST return a 16-char lowercase hex string."""
    rid = pipeline_state.generate_run_id()
    assert isinstance(rid, str)
    assert len(rid) == 16, f"run_id must be 16 chars, got {len(rid)}: {rid!r}"
    assert re.fullmatch(r"[0-9a-f]{16}", rid), f"run_id must be lowercase hex: {rid!r}"


# =============================================================================
# AC2: Lockfile via fcntl LOCK_NB; second acquire same process gets "lock held"
# =============================================================================


def test_ac2_first_acquire_returns_fd_second_returns_none():
    """First acquire on a fresh run_id MUST succeed (return fd).
    A second acquire of the same lockfile in the same process MUST return None
    (lock held), without blocking.
    """
    rid = pipeline_state.generate_run_id()
    lock_path = pipeline_state.get_lockfile_path(rid)
    fd1 = None
    fd2 = "sentinel"  # noqa: F841 -- must be reassigned by call below
    try:
        fd1 = pipeline_state.acquire_run_lock(rid)
        assert fd1 is not None, "First acquire MUST succeed and return an fd"
        assert isinstance(fd1, int)

        fd2 = pipeline_state.acquire_run_lock(rid)
        assert fd2 is None, (
            "Second acquire of the same lockfile in the same process MUST return None"
        )
    finally:
        if isinstance(fd1, int):
            pipeline_state.release_run_lock(fd1)
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass


def test_ac2_release_then_reacquire_succeeds():
    """After release_run_lock, the same run_id MUST be re-acquirable."""
    rid = pipeline_state.generate_run_id()
    lock_path = pipeline_state.get_lockfile_path(rid)
    try:
        fd1 = pipeline_state.acquire_run_lock(rid)
        assert fd1 is not None
        pipeline_state.release_run_lock(fd1)

        fd2 = pipeline_state.acquire_run_lock(rid)
        assert fd2 is not None, "Lock MUST be re-acquirable after release"
        pipeline_state.release_run_lock(fd2)
    finally:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass


# =============================================================================
# AC3: --resume <id> routes batch-* / 16-hex / legacy YYYYMMDD-HHMMSS correctly
# =============================================================================


@pytest.mark.parametrize(
    "arg,expected",
    [
        ("batch-20260101-abcd1234", "batch"),
        ("batch-foo", "batch"),
        ("a3f1b2c4d5e67890", "run_id"),
        ("0123456789abcdef", "run_id"),
        ("20260101-120000", "run_id_legacy"),
        ("19990101-235959", "run_id_legacy"),
    ],
)
def test_ac3_classify_resume_id_routes_correctly(arg, expected):
    """classify_resume_id MUST route each documented format to the correct class."""
    assert pipeline_state.classify_resume_id(arg) == expected


@pytest.mark.parametrize(
    "arg",
    [
        "",
        "not-a-valid-id",
        "ABCDEF0123456789",  # uppercase hex — spec says lowercase
        "a3f1b2c4d5e6789",  # 15 chars
        "a3f1b2c4d5e678901",  # 17 chars
        "20260101",  # date only, no time
        "garbage123",
    ],
)
def test_ac3_classify_resume_id_returns_invalid_for_unrecognized(arg):
    """Unrecognized formats MUST classify as 'invalid'."""
    assert pipeline_state.classify_resume_id(arg) == "invalid"


# =============================================================================
# AC4: Crash+resume via --resume <run_id> inherits completions
# =============================================================================


def test_ac4_resume_inherits_completions_without_manual_record(tmp_path, monkeypatch):
    """A crash followed by `--resume <run_id>` MUST inherit prior completions
    without requiring manual record_agent_completion calls.

    Behavioral test: write a state file with completions, then load it via
    the public load_pipeline API and verify completions are visible.
    """
    rid = pipeline_state.generate_run_id()

    # Simulate "before crash" — create state and complete a step.
    state = pipeline_state.create_pipeline(rid, "test feature")
    state = pipeline_state.advance(state, pipeline_state.Step.ALIGNMENT)
    state = pipeline_state.complete_step(state, pipeline_state.Step.ALIGNMENT, passed=True)
    pipeline_state.save_pipeline(state)

    # Simulate "after crash + --resume" — load by run_id.
    resumed = pipeline_state.load_pipeline(rid)
    assert resumed is not None, "load_pipeline(run_id) MUST find prior state"
    assert resumed.run_id == rid

    # The ALIGNMENT step's completion MUST be inherited (observed via the
    # public get_trace() API — no manual record_agent_completion required).
    trace = pipeline_state.get_trace(resumed)
    align_entries = [e for e in trace if e["step"] == pipeline_state.Step.ALIGNMENT.value]
    assert align_entries, (
        "Resumed pipeline MUST contain ALIGNMENT in its trace (completion inherited)"
    )
    assert align_entries[0]["status"] == pipeline_state.StepStatus.PASSED.value, (
        f"Resumed pipeline MUST inherit prior PASSED status, got {align_entries[0]['status']}"
    )

    # Cleanup
    try:
        state_path = pipeline_state.get_state_path(rid)
        if state_path.exists():
            state_path.unlink()
    except (AttributeError, OSError):
        pass


# =============================================================================
# AC5: Distinct run_ids across processes do not collide
# =============================================================================


def _generate_in_subprocess(_):
    """Worker for AC5: import the module fresh and generate one run_id."""
    sub_lib = str(
        Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
    )
    code = (
        "import sys; sys.path.insert(0, %r); "
        "from pipeline_state import generate_run_id; print(generate_run_id())"
    ) % sub_lib
    out = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    return out


def test_ac5_distinct_run_ids_across_processes():
    """run_ids generated in independent processes MUST NOT collide."""
    n = 16
    with multiprocessing.Pool(processes=4) as pool:
        ids = pool.map(_generate_in_subprocess, range(n))
    assert len(ids) == n
    assert len(set(ids)) == n, f"Collision detected across processes: {ids}"
    for rid in ids:
        assert re.fullmatch(r"[0-9a-f]{16}", rid), f"Invalid run_id from subprocess: {rid!r}"


def test_ac5_lockfile_paths_are_distinct_for_distinct_runids():
    """Distinct run_ids MUST produce distinct lockfile paths (no collision risk)."""
    rids = {pipeline_state.generate_run_id() for _ in range(50)}
    paths = {pipeline_state.get_lockfile_path(r) for r in rids}
    assert len(paths) == len(rids), "Lockfile paths must be 1:1 with run_ids"


# =============================================================================
# AC6: CHANGELOG documents transition from timestamp run_id to 16-char hex
# =============================================================================


def test_ac6_changelog_documents_runid_transition():
    """CHANGELOG.md MUST document the transition from the legacy timestamp
    run_id format (YYYYMMDD-HHMMSS) to the new 16-char hex format.

    We accept any of the following marker phrases as evidence of documentation:
      - mention of '#1047'
      - mention of 'token_hex' (the generation primitive)
      - mention of '16-char' / '16 char' / '16-character' hex
      - mention of 'YYYYMMDD-HHMMSS' alongside hex/run_id transition language
    """
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
    cl_lower = changelog.lower()
    markers = [
        "#1047",
        "issue 1047",
        "token_hex(8)",
        "16-char hex run_id",
        "16-character hex run_id",
        "16 char hex run_id",
    ]
    found = [m for m in markers if m.lower() in cl_lower]
    assert found, (
        "CHANGELOG.md MUST document the run_id transition from legacy "
        "timestamp (YYYYMMDD-HHMMSS) to 16-char hex format. "
        "Expected one of: " + ", ".join(repr(m) for m in markers)
    )


# =============================================================================
# AC7: Integration tests test_pipeline_run_id_resume.py +
#      test_pipeline_concurrent_runs.py exist
# =============================================================================


def test_ac7_integration_test_run_id_resume_exists():
    """Integration test file test_pipeline_run_id_resume.py MUST exist."""
    p = REPO_ROOT / "tests" / "integration" / "test_pipeline_run_id_resume.py"
    assert p.exists(), f"Integration test missing: {p}"
    body = p.read_text()
    assert "def test_" in body, "Integration test file must contain at least one test function"


def test_ac7_integration_test_concurrent_runs_exists():
    """Integration test file test_pipeline_concurrent_runs.py MUST exist."""
    p = REPO_ROOT / "tests" / "integration" / "test_pipeline_concurrent_runs.py"
    assert p.exists(), f"Integration test missing: {p}"
    body = p.read_text()
    assert "def test_" in body, "Integration test file must contain at least one test function"
