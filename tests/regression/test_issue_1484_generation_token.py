#!/usr/bin/env python3
"""Regression tests for Issue #1484 — generation-token compare-and-delete.

Protects the fix for the #1467 ABA race: an overlapping dispatch's SubagentStop
must NOT unconditionally disarm a sibling dispatch's still-in-flight sentinel.
The fix is a per-dispatch generation token minted at write() time and compared at
clear() time (compare-and-delete).

All tests route through an explicit ``repo_root`` (tmp_path) — never the live
``.claude`` tree — so they are hermetic and parallel-safe.

Issue: #1484
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import agent_dispatch_sentinel as ads  # noqa: E402


def _sentinel_path(root: Path) -> Path:
    return root / ".claude" / "local" / "active_agent_dispatch.json"


class TestIssue1484GenerationToken:
    """Compare-and-delete semantics for the agent-dispatch sentinel."""

    def test_clear_noop_when_generation_mismatch(self, tmp_path: Path) -> None:
        ads.write("implementer", repo_root=tmp_path, generation="GEN_A")
        # A different dispatch (GEN_B) tries to clear -> must be a no-op.
        ads.clear(repo_root=tmp_path, expected_generation="GEN_B")
        assert ads.is_active(repo_root=tmp_path) is True
        assert _sentinel_path(tmp_path).exists()

    def test_clear_deletes_when_generation_matches(self, tmp_path: Path) -> None:
        ads.write("implementer", repo_root=tmp_path, generation="GEN_A")
        ads.clear(repo_root=tmp_path, expected_generation="GEN_A")
        assert ads.is_active(repo_root=tmp_path) is False
        assert not _sentinel_path(tmp_path).exists()

    def test_clear_none_generation_unconditional_delete(self, tmp_path: Path) -> None:
        ads.write("implementer", repo_root=tmp_path, generation="GEN_A")
        # None expected_generation -> backward-compat unconditional unlink.
        ads.clear(repo_root=tmp_path, expected_generation=None)
        assert ads.is_active(repo_root=tmp_path) is False

    def test_clear_legacy_sentinel_no_generation_field(self, tmp_path: Path) -> None:
        # Pre-#1484 sentinel: no ``generation`` key at all.
        p = _sentinel_path(tmp_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        p.write_text(json.dumps({"agent": "x", "pid": 1, "timestamp": now, "armed_at": now}))
        # Even with an expected_generation, a legacy sentinel (no generation) is
        # deleted — we cannot prove another dispatch owns it.
        ads.clear(repo_root=tmp_path, expected_generation="ANYTHING")
        assert not p.exists()

    def test_overlapping_dispatch_race(self, tmp_path: Path) -> None:
        """Reproduces #1467: overlapping A/B dispatches share one sentinel.

        write(A), write(B) (B overwrites the single shared file). A's
        SubagentStop clears with expected=A -> no-op (B still owns it, gate stays
        armed). B's SubagentStop clears with expected=B -> deletes.
        """
        ads.write("implementer", repo_root=tmp_path, generation="A")
        ads.write("implementer", repo_root=tmp_path, generation="B")
        # A finishes first, but B is still in-flight -> must NOT disarm.
        ads.clear(repo_root=tmp_path, expected_generation="A")
        assert ads.is_active(repo_root=tmp_path) is True, (
            "A's SubagentStop disarmed B's in-flight sentinel (the #1467 bug)"
        )
        # B finishes -> now it disarms.
        ads.clear(repo_root=tmp_path, expected_generation="B")
        assert ads.is_active(repo_root=tmp_path) is False

    def test_session_id_asymmetry_correlation(self, tmp_path: Path, monkeypatch) -> None:
        """Env-first session_id resolution recovers the generation token.

        Covers both the asymmetric case (env CLAUDE_SESSION_ID != stdin
        session_id) AND the common no-op case (env == stdin) so the popper's
        env-first key matches the writer's env-first key in both.
        """
        sys.path.insert(0, str(_LIB))
        import subagent_invocation_cache as sic

        # --- Asymmetric case: env set, stdin differs. Writer keyed by env. ---
        monkeypatch.setenv("CLAUDE_SESSION_ID", "ENV_SESSION")
        stdin_session = "STDIN_SESSION"
        env_session = os.environ.get("CLAUDE_SESSION_ID") or stdin_session or "unknown"
        assert env_session == "ENV_SESSION"
        assert sic.cache_invocation(env_session, "implementer", generation="GEN_XYZ")
        # SubagentStop popper resolves env-first (Fix C) -> same key -> recovers gen.
        popper_session = os.environ.get("CLAUDE_SESSION_ID") or stdin_session or "unknown"
        entry = sic.pop_invocation(popper_session, preferred_subagent_type="implementer")
        assert entry is not None
        assert entry.get("generation") == "GEN_XYZ"

        # --- Common case: env == stdin -> env-first resolution is a no-op. ---
        monkeypatch.setenv("CLAUDE_SESSION_ID", "SAME_SESSION")
        stdin_same = "SAME_SESSION"
        writer_key = os.environ.get("CLAUDE_SESSION_ID") or stdin_same or "unknown"
        popper_key = os.environ.get("CLAUDE_SESSION_ID") or stdin_same or "unknown"
        assert writer_key == popper_key == "SAME_SESSION"
        assert sic.cache_invocation(writer_key, "implementer", generation="GEN_SAME")
        entry2 = sic.pop_invocation(popper_key, preferred_subagent_type="implementer")
        assert entry2 is not None
        assert entry2.get("generation") == "GEN_SAME"

    def test_overlapping_dispatch_cache_miss_clears_conservatively(
        self, tmp_path: Path
    ) -> None:
        """Documented degradation (residual amendment #1).

        On a genuine cache-miss the popper recovers no generation, so
        expected_generation is None and clear() unconditionally unlinks — which
        CAN ABA-disarm an overlapping sibling. This asserts the accepted
        backcompat gap so the behavior is intentional and locked, not a
        silent regression.
        """
        ads.write("implementer", repo_root=tmp_path, generation="A")
        ads.write("implementer", repo_root=tmp_path, generation="B")
        # Cache-miss path: expected_generation=None -> unconditional delete,
        # disarming B even though B is still in-flight.
        ads.clear(repo_root=tmp_path, expected_generation=None)
        assert ads.is_active(repo_root=tmp_path) is False, (
            "cache-miss None-clear is documented to disarm conservatively"
        )
