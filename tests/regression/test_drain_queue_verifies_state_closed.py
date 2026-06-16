"""Regression tests for /drain-queue STEP 12.5 post-push state=CLOSED verification.

The STEP 12.5 logic (documented in ``commands/drain-queue.md``) is:

1. For each issue N in ``DrainPendingMarker.read().issues``:
   call ``gh issue view N --json state --jq .state``.
2. If ANY N is not ``CLOSED``: call ``CircuitBreaker.record_failure()`` and
   STOP. Marker is NOT cleared (operator can inspect).
3. If ALL are CLOSED: call ``DrainPendingMarker.clear()``.

These tests exercise the Python primitives ``commands/drain-queue.md`` invokes
in its STEP 12.5 heredoc. They mock the ``gh issue view`` subprocess and
assert the marker-clear / circuit-breaker behavior matches.

Issue: drain-queue durability plan, acceptance criterion #5.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "plugins" / "autonomous-dev" / "lib"

if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from drain_pending import DrainPendingMarker  # noqa: E402
from drain_queue_state import CircuitBreaker  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """Create a fake repo with ``.claude/local/`` and chdir."""
    repo = tmp_path / "repo"
    (repo / ".claude" / "local").mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)
    return repo


def _gh_state_response(state: str) -> subprocess.CompletedProcess:
    """Build a CompletedProcess mimicking ``gh issue view N --json state --jq .state``."""
    return subprocess.CompletedProcess(
        args=["gh", "issue", "view"],
        returncode=0,
        stdout=f"{state}\n",
        stderr="",
    )


def _step_12_5_verify(
    repo: Path,
    issues: List[int],
    *,
    subprocess_run,
) -> Tuple[bool, List[int]]:
    """Replicates STEP 12.5 logic from commands/drain-queue.md.

    This mirrors the heredoc the markdown command runs at STEP 12.5. We
    extract it into a Python helper so the test can drive it with
    monkeypatched ``subprocess.run``.

    Returns (all_closed, unclosed_issues).
    """
    unclosed: List[int] = []
    for n in issues:
        r = subprocess_run(
            ["gh", "issue", "view", str(n), "--json", "state", "--jq", ".state"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0 or r.stdout.strip().upper() != "CLOSED":
            unclosed.append(n)
    if unclosed:
        CircuitBreaker.load(repo).record_failure()
        return (False, unclosed)
    DrainPendingMarker.clear(repo_root=repo)
    return (True, [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_step_12_5_all_closed_clears_marker(fake_repo: Path) -> None:
    """All cluster issues CLOSED → marker cleared, no breaker failure."""
    DrainPendingMarker.write(
        issues=[1160, 1161], cluster_tag="UNTAGGED", repo_root=fake_repo
    )
    breaker_before = CircuitBreaker.load(fake_repo)
    consec_before = breaker_before.consecutive_failures

    mock_run = MagicMock(side_effect=lambda *a, **kw: _gh_state_response("CLOSED"))
    all_closed, unclosed = _step_12_5_verify(
        fake_repo, [1160, 1161], subprocess_run=mock_run
    )
    assert all_closed is True
    assert unclosed == []
    # Marker was cleared.
    assert DrainPendingMarker.read(repo_root=fake_repo) is None
    # Circuit breaker NOT bumped.
    breaker_after = CircuitBreaker.load(fake_repo)
    assert breaker_after.consecutive_failures == consec_before


def test_step_12_5_one_open_records_failure_keeps_marker(
    fake_repo: Path,
) -> None:
    """Any OPEN issue → circuit breaker failure recorded, marker kept."""
    DrainPendingMarker.write(
        issues=[1160, 1161], cluster_tag="UNTAGGED", repo_root=fake_repo
    )
    breaker_before = CircuitBreaker.load(fake_repo)
    consec_before = breaker_before.consecutive_failures

    def fake_run(cmd, **_kwargs):
        # 1160 → CLOSED, 1161 → OPEN
        n = cmd[3]  # "gh issue view N"
        return _gh_state_response("CLOSED" if n == "1160" else "OPEN")

    mock_run = MagicMock(side_effect=fake_run)
    all_closed, unclosed = _step_12_5_verify(
        fake_repo, [1160, 1161], subprocess_run=mock_run
    )
    assert all_closed is False
    assert unclosed == [1161]
    # Marker retained for operator inspection.
    marker = DrainPendingMarker.read(repo_root=fake_repo)
    assert marker is not None
    assert marker.issues == [1160, 1161]
    # Circuit breaker bumped.
    breaker_after = CircuitBreaker.load(fake_repo)
    assert breaker_after.consecutive_failures == consec_before + 1


def test_step_12_5_gh_error_treated_as_unclosed(fake_repo: Path) -> None:
    """``gh issue view`` non-zero exit → treat as unclosed → fail."""
    DrainPendingMarker.write(
        issues=[42], cluster_tag="bug", repo_root=fake_repo
    )

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="auth failed"
        )

    mock_run = MagicMock(side_effect=fake_run)
    all_closed, unclosed = _step_12_5_verify(
        fake_repo, [42], subprocess_run=mock_run
    )
    assert all_closed is False
    assert unclosed == [42]
    # Marker retained.
    assert DrainPendingMarker.read(repo_root=fake_repo) is not None


def test_step_12_5_calls_gh_once_per_issue(fake_repo: Path) -> None:
    """STEP 12.5 issues exactly one ``gh issue view`` call per cluster issue."""
    DrainPendingMarker.write(
        issues=[100, 101, 102], cluster_tag="x", repo_root=fake_repo
    )
    mock_run = MagicMock(side_effect=lambda *a, **kw: _gh_state_response("CLOSED"))
    _step_12_5_verify(
        fake_repo, [100, 101, 102], subprocess_run=mock_run
    )
    assert mock_run.call_count == 3
    # Verify each call references the correct issue number.
    called_with = [call.args[0][3] for call in mock_run.call_args_list]
    assert set(called_with) == {"100", "101", "102"}


def test_step_12_5_passes_cwd_to_subprocess(fake_repo: Path) -> None:
    """STEP 12.5 ``gh`` calls MUST pass ``cwd=`` (Issue #1064 kwargs pattern)."""
    DrainPendingMarker.write(
        issues=[1], cluster_tag="x", repo_root=fake_repo
    )
    captured_kwargs: dict = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return _gh_state_response("CLOSED")

    mock_run = MagicMock(side_effect=fake_run)
    _step_12_5_verify(fake_repo, [1], subprocess_run=mock_run)
    assert "cwd" in captured_kwargs
    assert captured_kwargs["cwd"] == str(fake_repo)


def test_step_12_5_lowercase_closed_normalized(fake_repo: Path) -> None:
    """``gh`` returning lowercase ``"closed"`` → treated as CLOSED (case-insensitive)."""
    DrainPendingMarker.write(
        issues=[1], cluster_tag="x", repo_root=fake_repo
    )
    mock_run = MagicMock(
        side_effect=lambda *a, **kw: _gh_state_response("closed")
    )
    all_closed, unclosed = _step_12_5_verify(
        fake_repo, [1], subprocess_run=mock_run
    )
    assert all_closed is True
    assert unclosed == []


def test_step_12_5_no_marker_is_noop(fake_repo: Path) -> None:
    """No marker → STEP 12.5 has nothing to verify (operator state).

    This case is what happens after STEP 12 cleared the marker successfully.
    """
    # No DrainPendingMarker.write — verify reading returns None.
    assert DrainPendingMarker.read(repo_root=fake_repo) is None
    # Calling clear() is a no-op.
    assert DrainPendingMarker.clear(repo_root=fake_repo) is False
