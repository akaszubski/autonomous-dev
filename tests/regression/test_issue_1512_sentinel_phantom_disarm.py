"""Regression tests for Issue #1512 — phantom SubagentStop disarms a live sentinel.

MEASURED FAILURE (session cc5ba4af, 2026-08-15, activity log timeline):

    13:48:27.539  Agent/implementer dispatch      -> sentinel armed
    13:48:46.831  implementer Edit on plan_gate.py -> ALLOW
    13:48:53.122  implementer Edit                 -> ALLOW
    13:48:59.856  SubagentStop, result_word_count=5,
                  agent_transcript_path does NOT exist on disk
    13:48:59.993  implementer Edit                 -> DENY (#1296)

The sentinel was 33 seconds old against a 600s TTL, so expiry was not involved.
``unified_session_tracker`` recovered no generation from its invocation cache,
called ``clear(expected_generation=None)``, and that path unconditionally
unlinks -- disarming a LIVE dispatch mid-write. Every subsequent protected edit
was then attributed to the coordinator and denied.

Cost: six implementer dispatches to land a ~30-line patch, each leaving the
tree half-patched, and a revert impossible because a revert is itself a
protected write hitting the same gate.

These tests drive the real module. They fail before the fix and pass after.
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
def repo(tmp_path):
    """Isolated repo root so tests never touch the live sentinel."""
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _arm(repo_root, *, age_seconds=0.0, generation="gen-abc"):
    """Arm a sentinel and backdate it by age_seconds."""
    ads.write(agent_name="implementer", generation=generation, repo_root=repo_root)
    p = ads._path(repo_root)
    data = json.loads(p.read_text())
    now = time.time()
    data["timestamp"] = now - age_seconds
    data["armed_at"] = now - age_seconds
    p.write_text(json.dumps(data))
    return p


class TestPhantomStopCannotDisarmLiveDispatch:
    """The core defect: an anonymous clear must not kill a young sentinel."""

    def test_anonymous_clear_does_not_disarm_33_second_old_sentinel(self, repo):
        """THE MEASURED CASE. 33s old, anonymous clear -> must stay armed."""
        _arm(repo, age_seconds=33.0)
        assert ads.is_active(repo_root=repo) is True, "precondition: armed"

        # Phantom SubagentStop: no generation recovered from the invocation cache.
        ads.clear(repo_root=repo, expected_generation=None)

        assert ads.is_active(repo_root=repo) is True, (
            "A live 33-second-old dispatch was disarmed by an anonymous clear. "
            "This is the #1512 defect: it strands the implementer mid-patch."
        )

    def test_anonymous_clear_does_not_disarm_brand_new_sentinel(self, repo):
        """Age 0 -- the tightest case, a stop firing immediately after dispatch."""
        _arm(repo, age_seconds=0.0)
        ads.clear(repo_root=repo, expected_generation=None)
        assert ads.is_active(repo_root=repo) is True


class TestLegitimateClearsStillWork:
    """NEGATIVE CONTROLS. A fix that never clears is worse than the bug --
    it would leak sentinels and leave the hard floor permanently open."""

    def test_owner_clear_with_matching_generation_still_disarms(self, repo):
        """The genuine owner's stop carries its generation and MUST clear."""
        _arm(repo, age_seconds=5.0, generation="gen-owner")
        ads.clear(repo_root=repo, expected_generation="gen-owner")
        assert ads.is_active(repo_root=repo) is False, (
            "The real owner must still be able to disarm, or sentinels leak."
        )

    def test_force_clear_disarms_even_a_young_sentinel(self, repo):
        """Operator escape: force=True bypasses the age guard deliberately."""
        _arm(repo, age_seconds=0.0)
        ads.clear(repo_root=repo, expected_generation=None, force=True)
        assert ads.is_active(repo_root=repo) is False

    def test_sibling_generation_does_not_disarm(self, repo):
        """Pre-existing #1484 ABA guard must survive the fix."""
        _arm(repo, age_seconds=5.0, generation="gen-owner")
        ads.clear(repo_root=repo, expected_generation="gen-different")
        assert ads.is_active(repo_root=repo) is True

    def test_old_orphan_survives_anonymous_clear_but_ttl_still_bounds_the_leak(
        self, repo
    ):
        """An old orphan is NO LONGER reaped by an anonymous clear; TTL reaps it.

        CONTRACT REVERSAL (deliberate). This test previously asserted that an
        anonymous clear at 300s still unlinked, on the reasoning that refusing
        every anonymous clear would re-arm the #1447/#1448 sentinel-leak class.

        The leak concern is real but is now covered by a DIFFERENT mechanism:
        ``DEFAULT_TTL_SECONDS`` (600), not anonymous deletion. Age was never a
        sound discriminator -- real protected-path implementer runs take 3-5
        minutes, so any threshold short enough to reap orphans promptly also
        killed live dispatches. Identity is the discriminator: a caller that
        cannot say WHICH dispatch stopped may delete nothing.

        So this asserts both halves of the new contract:
          1. at 300s the sentinel SURVIVES an anonymous clear, and
          2. the leak is still bounded -- past DEFAULT_TTL_SECONDS it is gone.

        TRADEOFF (accepted): after an unidentified stop the sentinel may persist
        for up to 600s, during which the #1296 coordinator-vs-agent distinction
        is weaker. This is accepted because the previous behaviour broke
        legitimate work mid-dispatch and drove people to blanket bypasses, which
        is a strictly worse security posture than a bounded 600s window.
        """
        _arm(repo, age_seconds=300.0)
        ads.clear(repo_root=repo, expected_generation=None)
        assert ads.is_active(repo_root=repo) is True, (
            "An unidentified clear must not delete even an old sentinel -- "
            "identity, not age, authorizes deletion."
        )

        # The #1447/#1448 leak protection, now via the TTL backstop.
        _arm(repo, age_seconds=ads.DEFAULT_TTL_SECONDS + 60)
        ads.clear(repo_root=repo, expected_generation=None)
        assert ads.is_active(repo_root=repo) is False, (
            "TTL must still reap a genuinely abandoned sentinel -- otherwise "
            "refusing anonymous clears WOULD re-arm the #1447/#1448 leak class."
        )

    def test_ttl_still_reaps_a_protected_young_sentinel_eventually(self, repo):
        """Belt and braces: even if an anonymous clear is refused, the TTL
        backstop still expires the sentinel, so nothing leaks permanently."""
        _arm(repo, age_seconds=ads.DEFAULT_TTL_SECONDS + 60)
        assert ads.is_active(repo_root=repo) is False


class TestClearNeverRaises:
    """A failed disarm must never break a hook."""

    def test_clear_on_missing_sentinel_is_silent(self, repo):
        ads.clear(repo_root=repo, expected_generation=None)
        ads.clear(repo_root=repo, expected_generation="gen-x")

    def test_clear_on_malformed_sentinel_is_silent(self, repo):
        p = ads._path(repo)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{ not json")
        ads.clear(repo_root=repo, expected_generation=None)
        ads.clear(repo_root=repo, expected_generation="gen-x")
