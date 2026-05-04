"""
Tests for run_id support in pipeline_completion_state.py — Issue #1045.

Verifies:
- All 7 public functions accept optional keyword-only run_id parameter.
- Default (run_id=None) uses legacy sha256(session_id)[:8] hash path.
- When run_id provided, path is /tmp/pipeline_agent_completions_{run_id}.json.
- Round-trip read/write works with run_id.
- Two parallel run_ids do not see each other's completions.
- Legacy path (no run_id) still works as before.
- No callers in hooks/ or lib/ (other than pipeline_completion_state.py) were modified.

Issues: #1045, #1041
"""

import inspect
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Add lib to path
LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from pipeline_completion_state import (
    _state_file_path,
    get_completed_agents,
    get_plan_critic_skipped,
    get_research_skipped,
    record_agent_completion,
    record_plan_critic_skipped,
    record_pytest_gate_passed,
    record_research_skipped,
    verify_pipeline_agent_completions,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def session_id():
    """Unique session ID for test isolation (includes test-1045 marker)."""
    return f"test-1045-session-{os.getpid()}-{time.time_ns()}"


@pytest.fixture()
def run_id_a():
    """Unique run_id A for test isolation."""
    return f"run-A-test-1045-{os.getpid()}"


@pytest.fixture()
def run_id_b():
    """Unique run_id B for test isolation."""
    return f"run-B-test-1045-{os.getpid()}"


@pytest.fixture(autouse=True)
def cleanup_state_files(session_id, run_id_a, run_id_b):
    """Remove all state files created during a test."""
    yield
    for suffix in [
        session_id,
        run_id_a,
        run_id_b,
        "run-X-test-1045",
        f"run-X-test-1045-{os.getpid()}",
    ]:
        for candidate in Path("/tmp").glob(f"pipeline_agent_completions_*{suffix}*"):
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
    # Also clean up legacy hash-based files derived from our session_id
    import hashlib
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    legacy_path = Path(f"/tmp/pipeline_agent_completions_{h}.json")
    legacy_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# AC1: All 7 functions accept optional keyword-only run_id parameter
# --------------------------------------------------------------------------- #

_PUBLIC_FUNCTIONS_WITH_RUN_ID = [
    _state_file_path,
    record_agent_completion,
    get_completed_agents,
    record_plan_critic_skipped,
    record_research_skipped,
    record_pytest_gate_passed,
    verify_pipeline_agent_completions,
]


@pytest.mark.parametrize("func", _PUBLIC_FUNCTIONS_WITH_RUN_ID, ids=lambda f: f.__name__)
def test_all_functions_accept_run_id_keyword_only(func):
    """AC1: Every target function must have run_id as KEYWORD_ONLY with default None."""
    sig = inspect.signature(func)
    params = sig.parameters
    assert "run_id" in params, (
        f"{func.__name__} is missing the 'run_id' parameter. "
        f"Parameters found: {list(params)}"
    )
    p = params["run_id"]
    assert p.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"{func.__name__}.run_id must be KEYWORD_ONLY (after *), "
        f"got kind={p.kind.name}"
    )
    assert p.default is None, (
        f"{func.__name__}.run_id must default to None, got default={p.default!r}"
    )


# --------------------------------------------------------------------------- #
# AC2: Default (run_id=None) uses legacy sha256 hash path
# --------------------------------------------------------------------------- #


def test_default_path_uses_legacy_sha256_hash(session_id):
    """AC2: Without run_id, _state_file_path uses sha256(session_id)[:8] hash."""
    import hashlib

    path = _state_file_path(session_id)
    expected_hash = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    expected_filename = f"pipeline_agent_completions_{expected_hash}.json"

    assert path.name == expected_filename, (
        f"Expected filename {expected_filename!r}, got {path.name!r}"
    )
    assert re.match(r"pipeline_agent_completions_[0-9a-f]{8}\.json", path.name), (
        f"Path name {path.name!r} does not match legacy pattern"
    )
    assert str(path).startswith("/tmp/"), f"Expected /tmp/ prefix, got {path}"


# --------------------------------------------------------------------------- #
# AC3: run_id path format
# --------------------------------------------------------------------------- #


def test_run_id_path_format():
    """AC3: With run_id, path is /tmp/pipeline_agent_completions_{run_id}.json exactly."""
    test_run_id = "abc123def456789a"
    path = _state_file_path("any-session", run_id=test_run_id)
    expected = Path(f"/tmp/pipeline_agent_completions_{test_run_id}.json")
    assert path == expected, f"Expected {expected}, got {path}"


def test_run_id_path_format_various():
    """AC3: run_id path format holds for different run_id values."""
    for run_id in ["run-X-test-1045", "0123456789abcdef", "my-run-123"]:
        path = _state_file_path("ignored-session", run_id=run_id)
        assert path == Path(f"/tmp/pipeline_agent_completions_{run_id}.json"), (
            f"Unexpected path for run_id={run_id!r}: {path}"
        )


# --------------------------------------------------------------------------- #
# AC5 (isolation): Round-trip with run_id
# --------------------------------------------------------------------------- #


def test_record_and_get_with_run_id_round_trip(session_id):
    """AC5: Write completion under run_id, read it back; legacy path does NOT see it."""
    run_id = f"run-X-test-1045-{os.getpid()}"

    # Write under run_id
    record_agent_completion(
        session_id, "researcher-local", issue_number=0, success=True, run_id=run_id
    )

    # Read back WITH the same run_id — must see the completion
    completed_with_run_id = get_completed_agents(session_id, issue_number=0, run_id=run_id)
    assert "researcher-local" in completed_with_run_id, (
        f"researcher-local not found in run_id-scoped read: {completed_with_run_id}"
    )

    # Read WITHOUT run_id (legacy path) — must NOT see it (different file)
    completed_legacy = get_completed_agents(session_id, issue_number=0)
    assert "researcher-local" not in completed_legacy, (
        f"Completion leaked from run_id-scoped file to legacy path: {completed_legacy}"
    )


# --------------------------------------------------------------------------- #
# AC5: Parallel run_ids are isolated from each other
# --------------------------------------------------------------------------- #


def test_parallel_run_ids_isolated(session_id, run_id_a, run_id_b):
    """AC5: Two concurrent run_ids do not see each other's completions."""
    # Record different agents under each run_id
    record_agent_completion(session_id, "planner", issue_number=0, run_id=run_id_a)
    record_agent_completion(session_id, "implementer", issue_number=0, run_id=run_id_b)

    # run-A sees only its own agent
    agents_a = get_completed_agents(session_id, issue_number=0, run_id=run_id_a)
    assert "planner" in agents_a, f"planner missing from run-A: {agents_a}"
    assert "implementer" not in agents_a, (
        f"implementer from run-B leaked into run-A: {agents_a}"
    )

    # run-B sees only its own agent
    agents_b = get_completed_agents(session_id, issue_number=0, run_id=run_id_b)
    assert "implementer" in agents_b, f"implementer missing from run-B: {agents_b}"
    assert "planner" not in agents_b, (
        f"planner from run-A leaked into run-B: {agents_b}"
    )


# --------------------------------------------------------------------------- #
# AC4: Back-compat — legacy path works unchanged
# --------------------------------------------------------------------------- #


def test_back_compat_legacy_path_unchanged(session_id):
    """AC4: Callers without run_id get exactly the same behavior as before."""
    # Write without run_id
    record_agent_completion(session_id, "planner", issue_number=0, success=True)

    # Read without run_id — must see it
    completed = get_completed_agents(session_id, issue_number=0)
    assert "planner" in completed, (
        f"Legacy round-trip broken: planner not in {completed}"
    )

    # Verify the actual file has the sha256 hash name
    import hashlib
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    legacy_path = Path(f"/tmp/pipeline_agent_completions_{h}.json")
    assert legacy_path.exists(), f"Legacy state file not found at {legacy_path}"


# --------------------------------------------------------------------------- #
# AC6: No existing callers modified
# --------------------------------------------------------------------------- #


def test_no_existing_callers_modified():
    """AC6: git diff master shows no changes to hooks/ or lib/ except pipeline_completion_state.py."""
    result = subprocess.run(
        ["git", "diff", "master", "--name-only",
         "plugins/autonomous-dev/hooks/",
         "plugins/autonomous-dev/lib/"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"git diff failed: {result.stderr}"

    changed_files = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    # Filter out pipeline_completion_state.py — that's the one we're allowed to change
    unexpected_changes = [
        f for f in changed_files
        if "pipeline_completion_state.py" not in f
    ]

    assert unexpected_changes == [], (
        f"Unexpected changes to hooks/ or lib/ callers: {unexpected_changes}"
    )


# --------------------------------------------------------------------------- #
# Security: run_id validation (traversal rejection) — Security Finding 1 & 2
# --------------------------------------------------------------------------- #


def test_run_id_rejects_path_traversal():
    """Security: run_id with .. sequences raises ValueError (path traversal)."""
    with pytest.raises(ValueError, match="invalid characters"):
        _state_file_path("any", run_id="../../etc/passwd")


def test_run_id_rejects_absolute_path():
    """Security: run_id starting with / raises ValueError (absolute path injection)."""
    with pytest.raises(ValueError, match="invalid characters"):
        _state_file_path("any", run_id="/etc/passwd")


def test_run_id_rejects_overlength():
    """Security: run_id longer than 64 chars raises ValueError."""
    with pytest.raises(ValueError, match="invalid characters"):
        _state_file_path("any", run_id="a" * 100)


@pytest.mark.parametrize("bad_run_id", ["foo bar", "foo;rm", "foo$x"])
def test_run_id_rejects_special_chars(bad_run_id: str):
    """Security: run_id with spaces, semicolons, or shell-special chars raises ValueError."""
    with pytest.raises(ValueError, match="invalid characters"):
        _state_file_path("any", run_id=bad_run_id)


@pytest.mark.parametrize("good_run_id", ["abc123", "run-A-test", "A_B-1234567890abcdef"])
def test_run_id_accepts_valid_formats(good_run_id: str):
    """Security: valid run_id values are accepted without raising."""
    path = _state_file_path("any", run_id=good_run_id)
    assert path == Path(f"/tmp/pipeline_agent_completions_{good_run_id}.json")


def test_get_research_skipped_with_run_id(session_id):
    """FINDING-1: record_research_skipped with run_id is readable only via same run_id."""
    run_id = f"run-C-test-1045-{os.getpid()}"
    try:
        # Write skip flag with run_id
        record_research_skipped(session_id, issue_number=0, run_id=run_id)

        # Reading WITH run_id must return True
        assert get_research_skipped(session_id, issue_number=0, run_id=run_id) is True, (
            "get_research_skipped with matching run_id should return True"
        )

        # Reading WITHOUT run_id (legacy path) must return False — different file
        assert get_research_skipped(session_id, issue_number=0) is False, (
            "get_research_skipped without run_id should return False (different file)"
        )
    finally:
        for candidate in Path("/tmp").glob(f"pipeline_agent_completions_*{run_id}*"):
            candidate.unlink(missing_ok=True)


def test_get_plan_critic_skipped_with_run_id(session_id):
    """FINDING-1: record_plan_critic_skipped with run_id is readable only via same run_id."""
    run_id = f"run-D-test-1045-{os.getpid()}"
    try:
        # Write skip flag with run_id
        record_plan_critic_skipped(session_id, issue_number=0, run_id=run_id)

        # Reading WITH run_id must return True
        assert get_plan_critic_skipped(session_id, issue_number=0, run_id=run_id) is True, (
            "get_plan_critic_skipped with matching run_id should return True"
        )

        # Reading WITHOUT run_id (legacy path) must return False — different file
        assert get_plan_critic_skipped(session_id, issue_number=0) is False, (
            "get_plan_critic_skipped without run_id should return False (different file)"
        )
    finally:
        for candidate in Path("/tmp").glob(f"pipeline_agent_completions_*{run_id}*"):
            candidate.unlink(missing_ok=True)
