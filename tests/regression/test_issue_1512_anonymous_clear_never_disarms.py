"""Regression tests for Issue #1512 — an anonymous clear must NEVER disarm.

Companion to ``test_issue_1512_sentinel_phantom_disarm.py`` (the earlier partial
fix). This file covers the AGE-INDEPENDENCE contract specifically; keep both.

Issue #1484 added compare-and-delete so a ``SubagentStop`` cannot disarm a
*different* in-flight dispatch: ``clear(expected_generation=G)`` is a no-op
unless ``G`` matches the sentinel's recorded generation. That works.

But ``unified_session_tracker`` passes ``expected_generation=None`` whenever its
invocation cache misses, and ``None`` routed to an anonymous path that ignored
the comparison entirely. The first fix attempt for #1512 tried to contain that
with a minimum-age floor (``MIN_ANONYMOUS_CLEAR_AGE_SECONDS = 120``); it was
committed but did not close the issue. A timing heuristic applied to a
correctness problem fails in exactly the case that matters — it protects
dispatches younger than 120s and abandons everything older, while a
protected-path implementer run routinely takes 3-5 minutes:

    MIN_ANONYMOUS_CLEAR_AGE_SECONDS = 120 ; DEFAULT_TTL_SECONDS = 600

    live dispatch  30s old, clear(expected_generation=None)      -> survives True
    live dispatch 180s old, clear(expected_generation=None)      -> survives False  <- BUG
    live dispatch 180s old, clear(expected_generation="OTHER")   -> survives True
    live dispatch 180s old, clear(expected_generation=<match>)   -> survives False

Consequence: a still-running implementer loses its authorization mid-run and
every later protected-path edit is refused as a "coordinator direct edit".

The fix: when the caller cannot say WHICH dispatch stopped, it clears nothing —
regardless of age. ``DEFAULT_TTL_SECONDS`` (600) remains the backstop that reaps
genuinely abandoned sentinels, so "never clear anonymously" is not a leak.

The load-bearing test here is the 180s case. An equivalent test at 30s passes
under both the old and the new code and proves nothing.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import agent_dispatch_sentinel as ads  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Isolated repo root so tests never touch the live ``.claude/local/`` sentinel."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _arm(repo_root: Path, *, age_seconds: float = 0.0, generation: str = "gen-live") -> Path:
    """Arm a sentinel and backdate it by ``age_seconds`` (no sleep)."""
    ads.write(agent_name="implementer", generation=generation, repo_root=repo_root)
    p = ads._path(repo_root)
    data = json.loads(p.read_text())
    now = time.time()
    data["timestamp"] = now - age_seconds
    data["armed_at"] = now - age_seconds
    p.write_text(json.dumps(data))
    return p


class TestAnonymousClearNeverDisarms:
    """An unidentified stop must leave the sentinel alone at ANY age."""

    def test_anonymous_clear_does_not_disarm_180_second_old_sentinel(self, repo: Path) -> None:
        """THE TEST THAT WOULD HAVE CAUGHT THE #1512 RECURRENCE.

        180s is past the old 120s floor and well inside the 600s TTL — the
        window a real protected-path implementer run lives in. Under the old
        age-floor semantics this sentinel was unlinked mid-dispatch.
        """
        _arm(repo, age_seconds=180.0)
        assert ads.is_active(repo_root=repo) is True, "precondition: armed and live"

        ads.clear(repo_root=repo, expected_generation=None)

        assert ads.is_active(repo_root=repo) is True, (
            "A live 180-second-old dispatch was disarmed by an anonymous clear. "
            "The old MIN_ANONYMOUS_CLEAR_AGE_SECONDS floor abandons exactly the "
            "dispatches that take longest — the #1512 defect."
        )

    def test_anonymous_clear_does_not_disarm_30_second_old_sentinel(self, repo: Path) -> None:
        """The old floor's case still holds (passes under both old and new code)."""
        _arm(repo, age_seconds=30.0)
        ads.clear(repo_root=repo, expected_generation=None)
        assert ads.is_active(repo_root=repo) is True


class TestCompareAndDeleteUnaffected:
    """#1484 compare-and-delete semantics must survive the #1512 fix."""

    def test_wrong_generation_leaves_sentinel_armed(self, repo: Path) -> None:
        """A sibling dispatch's stop must not disarm this dispatch."""
        _arm(repo, age_seconds=180.0, generation="gen-live")
        ads.clear(repo_root=repo, expected_generation="WRONG")
        assert ads.is_active(repo_root=repo) is True, (
            "compare-and-delete regressed: a non-matching generation disarmed the sentinel."
        )

    def test_matching_generation_does_clear(self, repo: Path) -> None:
        """NEGATIVE CONTROL: the fix must not make the sentinel un-clearable."""
        _arm(repo, age_seconds=180.0, generation="gen-live")
        ads.clear(repo_root=repo, expected_generation="gen-live")
        assert ads.is_active(repo_root=repo) is False, (
            "The genuine owner must still disarm, or every dispatch leaks a sentinel."
        )


class TestEscapeHatchAndBackstop:
    """"Never clear anonymously" must remain distinguishable from a leak."""

    def test_force_clear_still_disarms(self, repo: Path) -> None:
        """Operator recovery escape hatch survives the fix."""
        _arm(repo, age_seconds=180.0)
        ads.clear(repo_root=repo, expected_generation=None, force=True)
        assert ads.is_active(repo_root=repo) is False

    def test_ttl_backstop_still_reaps_abandoned_sentinel(self, repo: Path) -> None:
        """NEGATIVE CONTROL: without this, "never clear" is indistinguishable
        from a permanent leak. A sentinel past DEFAULT_TTL_SECONDS is inactive."""
        _arm(repo, age_seconds=ads.DEFAULT_TTL_SECONDS + 60)
        assert ads.is_active(repo_root=repo) is False, (
            "TTL backstop broken: an abandoned sentinel would block protected "
            "writes forever now that anonymous clears are refused."
        )
