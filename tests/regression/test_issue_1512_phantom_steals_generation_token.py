#!/usr/bin/env python3
"""Regression tests for Issue #1512 — the phantom SubagentStop steals the
generation token, so the #1484 compare-and-delete guard is satisfied by the
wrong caller and a LIVE dispatch is disarmed.

WHY THIS FILE EXISTS ALONGSIDE test_issue_1512_sentinel_phantom_disarm.py
-------------------------------------------------------------------------
That file closed the ``expected_generation is None`` path: an *anonymous* clear
now refuses to unlink at any age. It is a real fix and it holds. It is not the
whole defect, and measurement shows it does not close the dominant path.

The dominant path never reaches the anonymous branch at all. A phantom
SubagentStop pops the #1087 invocation cache FIRST, recovers the live
dispatch's generation token, and then calls
``clear(expected_generation=<the live token>)`` — which matches, and unlinks.
The token is handed out by ``subagent_type``, not by dispatch identity, so any
stop naming the right agent type collects it.

MEASURED (session cc5ba4af, activity logs 2026-08-15 + 2026-08-17)
------------------------------------------------------------------
102 typed SubagentStop events, partitioned by whether ``agent_transcript_path``
names a file that exists on disk:

    PHANTOM (transcript never written)   50   ALL cache_HIT  (duration_ms > 0)
    REAL    (transcript on disk)         52   ALL cache_MISS (duration_ms == 0)

102/102 separation, no overlap. Retention does not explain it: every one of
these records postdates the oldest surviving transcript in the session
directory, and phantom/real transcript basenames are disjoint (50 vs 52
distinct names, zero shared). Word counts separate cleanly too — phantom max 6,
real min 12.

Read that table again in the direction that matters: **the phantom always wins
the cache, and the real stop always loses it.** So today the phantom collects
the generation token and disarms the sentinel, while the genuine owner arrives
to an empty queue, produces no token, and (post-fix) correctly refuses to clear
anything. The two halves of the correlation are the same event: the phantom's
theft is what causes the owner's miss.

Collateral damage beyond the sentinel: ``duration_ms`` is attributed to the
phantom, so every real agent completion is logged with duration 0 — the exact
telemetry corruption #1087 was written to prevent.

WHY THE EXISTING #1414 GUARD DOES NOT CATCH THIS
-------------------------------------------------
``unified_session_tracker`` already knows the phantom-then-real shape — that is
what ``_PHANTOM_DEDUP_CACHE`` (Issue #1414) is for. Two problems:

  1. ORDERING. It runs at ~line 1432, roughly 180 lines AFTER the cache pop
     (~1251) and the sentinel clear (~1272). By the time anything classifies
     the event as a phantom, the token is spent and the sentinel is gone.
  2. PROCESS LIFETIME. It is a module-level dict, and every SubagentStop is a
     fresh hook subprocess, so it is empty on arrival. Across six months of
     activity logs it produced 6 ``__phantom_dedup_skip__`` records total.

THE INVARIANT UNDER TEST
------------------------
A SubagentStop that names a transcript which does not exist on disk is not a
dispatch completion. It must not pop the invocation cache and must not clear
the sentinel.

The empty-path case is deliberately excluded from that rule — see
``test_stop_with_empty_transcript_path_still_pops``. Only 3 stops in the entire
corpus had an empty path; treating "unknown" as "phantom" would break the #1087
recovery contract for a case the measurement says is negligible.

STATUS: lands RED on purpose. A gate committed green proves nothing.

Issue: #1512
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_LIB = _ROOT / "plugins" / "autonomous-dev" / "lib"
_HOOKS = _ROOT / "plugins" / "autonomous-dev" / "hooks"
for _p in (str(_LIB), str(_HOOKS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_dispatch_sentinel as ads  # noqa: E402
import subagent_invocation_cache as sic  # noqa: E402

_SESSION = "phantom-token-1512"
_GENERATION = "GEN-LIVE-DISPATCH"


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """Drive the real SubagentStop hook against a fully isolated tree.

    Everything that would otherwise touch shared state — the sentinel, the
    invocation cache, the dedup markers, the activity log, the pipeline
    completion store — is routed into ``tmp_path``. ``HOME`` is redirected too,
    because ``_validate_transcript_path`` only accepts paths under
    ``~/.claude`` and the tests need transcripts they are allowed to create.
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    sentinel_root = tmp_path / "repo"
    (sentinel_root / ".claude" / "local").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        ads, "_path", lambda repo_root=None: (
            Path(repo_root) if repo_root is not None else sentinel_root
        ) / ads._SENTINEL_REL
    )

    cache_file = tmp_path / "invocations.json"
    monkeypatch.setattr(sic, "cache_path", lambda sid: cache_file)

    if "unified_session_tracker" in sys.modules:
        ust = importlib.reload(sys.modules["unified_session_tracker"])
    else:
        ust = importlib.import_module("unified_session_tracker")

    monkeypatch.setattr(ust, "_pop_cached_subagent_invocation", sic.pop_invocation)
    monkeypatch.setattr(ust, "_DEFAULT_MARKER_DIR", tmp_path)

    entries: list[dict] = []
    monkeypatch.setattr(
        ust, "_write_jsonl_entry", lambda **kw: (entries.append(kw) or True)
    )
    monkeypatch.setattr(ust, "track_basic_session", lambda *a, **k: None)
    monkeypatch.setattr(ust, "track_pipeline_completion", lambda *a, **k: None)
    monkeypatch.setattr(ust, "_get_current_issue_number", lambda: None)

    import pipeline_completion_state as pcs

    monkeypatch.setattr(pcs, "record_agent_completion", lambda **kw: None)

    transcripts = tmp_path / ".claude" / "projects" / "p" / "subagents"
    transcripts.mkdir(parents=True, exist_ok=True)

    class _H:
        module = ust
        entries_written = entries
        transcript_dir = transcripts
        repo = sentinel_root

        @staticmethod
        def arm(generation: str = _GENERATION) -> None:
            """Arm the sentinel the way a PreToolUse Agent dispatch does."""
            ads.write("implementer", repo_root=sentinel_root, generation=generation)

        @staticmethod
        def enqueue(agent: str = "implementer", generation: str = _GENERATION) -> None:
            """Record the dispatch in the #1087 invocation cache."""
            sic.cache_invocation(
                _SESSION, agent, start_time=time.time() - 40.0, generation=generation
            )

        @staticmethod
        def phantom_transcript() -> str:
            """A transcript path that is never written — the phantom signature."""
            return str(transcripts / "agent-phantom0000000000.jsonl")

        @staticmethod
        def real_transcript() -> str:
            """A transcript that exists on disk, as a live agent's does."""
            p = transcripts / "agent-real00000000000000.jsonl"
            p.write_text(
                json.dumps({"type": "assistant", "message": {"content": "work"}}) + "\n"
            )
            return str(p)

        @staticmethod
        def fire(agent_type: str, transcript_path: str, message: str) -> None:
            """Deliver one SubagentStop to the real hook entry point."""
            payload = json.dumps(
                {
                    "hook_event_name": "SubagentStop",
                    "agent_type": agent_type,
                    "session_id": _SESSION,
                    "agent_transcript_path": transcript_path,
                    "last_assistant_message": message,
                }
            )
            with patch("sys.stdin", StringIO(payload)):
                with patch.dict(
                    os.environ, {"CLAUDE_SESSION_ID": _SESSION}, clear=False
                ):
                    ust.main()

    return _H


# The five-word result the measured phantoms carried.
_PHANTOM_MESSAGE = "Agent completed without producing output"
_REAL_MESSAGE = " ".join(["substantive"] * 60)


class TestPhantomStopMustNotClaimTheDispatch:
    """The unfixed root cause: identity is inferred from ``subagent_type``."""

    def test_phantom_stop_does_not_pop_the_invocation_cache(self, harness):
        """The token belongs to the live dispatch. A phantom may not take it.

        FAILS TODAY: ``pop_invocation(preferred_subagent_type="implementer")``
        matches on type alone, so the phantom drains the queue entry that the
        genuine stop needs.
        """
        harness.arm()
        harness.enqueue()

        harness.fire("implementer", harness.phantom_transcript(), _PHANTOM_MESSAGE)

        remaining = sic.peek_queue(_SESSION)
        assert len(remaining) == 1, (
            "A phantom SubagentStop consumed the live dispatch's invocation "
            "entry. Everything downstream — the generation token, duration_ms, "
            "the completeness gate — is now attributed to an event that never "
            "ran an agent."
        )
        assert remaining[0]["generation"] == _GENERATION

    def test_phantom_stop_does_not_disarm_a_live_sentinel(self, harness):
        """THE MEASURED PRODUCTION FAILURE.

        The sentinel is armed and a real implementer is mid-patch. A phantom
        stop arrives naming the same agent type. Today it pops the token,
        passes the #1484 compare-and-delete, and unlinks — and the implementer's
        next protected write is denied as a coordinator edit, stranding a
        half-applied patch that cannot be reverted (a revert is itself a
        protected write).
        """
        harness.arm()
        harness.enqueue()
        assert ads.is_active(repo_root=harness.repo) is True, "precondition: armed"

        harness.fire("implementer", harness.phantom_transcript(), _PHANTOM_MESSAGE)

        assert ads.is_active(repo_root=harness.repo) is True, (
            "A phantom SubagentStop disarmed a live dispatch. The #1484 "
            "generation token did not stop it, because the token was handed "
            "out by subagent_type rather than by dispatch identity."
        )

    def test_real_stop_after_phantom_still_completes_the_dispatch(self, harness):
        """End-to-end in production order: phantom first, then the real stop.

        Both halves of the measured correlation must reverse. The real stop
        must be the one that gets the cache entry (hence a non-zero duration),
        and the sentinel must be disarmed exactly once, by its owner.
        """
        harness.arm()
        harness.enqueue()

        harness.fire("implementer", harness.phantom_transcript(), _PHANTOM_MESSAGE)
        assert ads.is_active(repo_root=harness.repo) is True, (
            "sentinel must survive the phantom"
        )

        harness.fire("implementer", harness.real_transcript(), _REAL_MESSAGE)

        assert ads.is_active(repo_root=harness.repo) is False, (
            "The genuine owner's stop must still disarm. A fix that leaves the "
            "sentinel permanently armed is worse than the bug — it holds the "
            "#1435 hard floor open."
        )

        real_entries = [
            e
            for e in harness.entries_written
            if e.get("subagent_type") == "implementer"
            and not str(e.get("subagent_type", "")).startswith("__")
        ]
        assert real_entries, "the real completion must be recorded"
        assert real_entries[-1]["duration_ms"] > 0, (
            "duration_ms landed on the phantom instead of the real agent — the "
            "#1087 telemetry corruption this cache was written to prevent."
        )


class TestNegativeControls:
    """A probe that cannot fail cannot inform, and an over-broad fix is a
    second defect wearing the first one's clothes."""

    def test_real_stop_alone_pops_and_disarms(self, harness):
        """No phantom involved. The ordinary path must be untouched."""
        harness.arm()
        harness.enqueue()

        harness.fire("implementer", harness.real_transcript(), _REAL_MESSAGE)

        assert sic.peek_queue(_SESSION) == [], "the real stop must consume its entry"
        assert ads.is_active(repo_root=harness.repo) is False, (
            "the genuine owner must be able to disarm"
        )

    def test_stop_with_empty_transcript_path_still_pops(self, harness):
        """``agent_transcript_path == ""`` is UNKNOWN, not phantom.

        Claude Code omits the path on a small minority of genuine stops (3 in
        the entire measured corpus). The #1087 cache exists precisely to
        recover identity for those. A fix that treats a missing path as proof
        of a phantom would re-break the #1387/#1412 false-negative class and
        block legitimate commits at the #802 completeness gate.
        """
        harness.arm()
        harness.enqueue()

        harness.fire("implementer", "", _REAL_MESSAGE)

        assert sic.peek_queue(_SESSION) == [], (
            "An empty transcript path must NOT be classified as a phantom — "
            "the #1087 recovery contract depends on it."
        )

    def test_sentinel_for_a_different_dispatch_is_untouched(self, harness):
        """Pre-existing #1484 ABA guard must survive the fix."""
        harness.arm(generation="GEN-OTHER-DISPATCH")
        harness.enqueue(generation=_GENERATION)

        harness.fire("implementer", harness.real_transcript(), _REAL_MESSAGE)

        assert ads.is_active(repo_root=harness.repo) is True, (
            "a stop carrying one generation must never disarm another's sentinel"
        )


class TestIsActiveIsSideEffectFree:
    """Acceptance criterion 4 of #1512: measuring the gate must not perturb it.

    ``is_active()`` unlinks stale sentinels as a side effect of what reads like
    a pure predicate. Any diagnostic that inspects a sentinel destroys it,
    which is a large part of why this class of bug took five dispatches to
    characterise — the instrument consumed its own evidence.
    """

    def test_is_active_does_not_delete_a_stale_sentinel(self, tmp_path):
        """FAILS TODAY: the stale branch calls ``p.unlink()``."""
        ads.write("implementer", repo_root=tmp_path, generation="GEN-STALE")
        p = tmp_path / ads._SENTINEL_REL
        data = json.loads(p.read_text())
        old = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
        data["timestamp"] = old
        data["armed_at"] = old
        p.write_text(json.dumps(data))

        assert ads.is_active(repo_root=tmp_path) is False
        assert p.exists(), (
            "is_active() deleted the sentinel it was asked to describe. "
            "Reaping belongs in an explicit reaper, not in a predicate."
        )

    def test_is_active_is_idempotent(self, tmp_path):
        """Two identical questions must get two identical answers."""
        ads.write("implementer", repo_root=tmp_path, generation="GEN-STALE")
        p = tmp_path / ads._SENTINEL_REL
        data = json.loads(p.read_text())
        old = time.time() - (ads.DEFAULT_TTL_SECONDS + 60)
        data["timestamp"] = old
        data["armed_at"] = old
        p.write_text(json.dumps(data))

        first = ads.is_active(repo_root=tmp_path)
        second = ads.is_active(repo_root=tmp_path)
        assert first == second is False
        assert p.exists()
