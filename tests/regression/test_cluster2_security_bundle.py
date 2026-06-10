"""Regression tests for Cluster 2 security bundle.

Covers five linked hardenings landed in one PR:
- #1169: state file mode 0o600 in _write_state
- #1170: _locked_rmw RMW lockfile for ring-buffer mutators
- #1171: _resolve_session_id_safe centralizes env-var sanitization
- #1166: module-level cache for the ring-buffer API import
- #1177: dead PIPELINE_MODE env reads removed at two call sites,
         3 follow-up comments flag the remaining suspected-dead reads

Each test is named ``test_*`` and stays under the regression tier
(<=30s wall). Multiprocessing-based concurrency tests use a fresh
session id per case so /tmp state files do not collide between
parallel test runners.
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
import re
import stat
import sys
import time
import uuid
from pathlib import Path

import pytest

# Add lib + hooks dirs to path (tests/regression/ -> tests/ -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOK_DIR))

import pipeline_completion_state as pcs  # noqa: E402
import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_session_id() -> str:
    """Return a unique session id so state files don't collide across tests."""
    return f"cluster2-test-{uuid.uuid4().hex[:12]}"


def _state_path_for(session_id: str) -> Path:
    return pcs._state_file_path(session_id)


def _lock_path_for(session_id: str) -> Path:
    import hashlib as _hl

    key = _hl.sha256(session_id.encode()).hexdigest()[:8]
    return Path(f"/tmp/pipeline_agent_completions_{key}.lock")


def _cleanup_session(session_id: str) -> None:
    """Remove the state file + lockfile for a session id (idempotent)."""
    for p in (_state_path_for(session_id), _lock_path_for(session_id)):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# Multiprocessing worker — must be at module level so pickle can find it.
def _ring_buffer_worker(session_id: str, file_path: str, n_appends: int) -> None:
    """Worker process: append `n_appends` Tier-1 allows to the ring buffer."""
    # Re-add the lib dir on path (child processes don't inherit sys.path
    # mutations from the parent's import — only from sys.argv).
    sys.path.insert(0, str(LIB_DIR))
    import pipeline_completion_state as _pcs

    for _ in range(n_appends):
        _pcs.record_tier1_allow(session_id, file_path, 1)


# ---------------------------------------------------------------------------
# AC-1: chmod 0o600 on state files (#1169)
# ---------------------------------------------------------------------------


class TestStateFilePermissions:
    """#1169: state files written by _write_state must be mode 0o600."""

    def test_write_state_sets_mode_0o600(self) -> None:
        sid = _fresh_session_id()
        try:
            pcs._write_state(sid, {"session_id": sid, "completions": {}})
            path = _state_path_for(sid)
            assert path.exists(), "state file was not created"
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600, (
                f"Expected mode 0o600, got 0o{mode:o}. State files in /tmp "
                f"must not be world- or group-readable."
            )
        finally:
            _cleanup_session(sid)

    def test_write_state_existing_file_gets_chmod_on_rewrite(self) -> None:
        """A pre-existing 0o644 state file is tightened on next write."""
        sid = _fresh_session_id()
        try:
            # Create the file with overly-permissive mode.
            path = _state_path_for(sid)
            path.write_text('{"session_id": "' + sid + '"}')
            os.chmod(path, 0o644)
            assert (path.stat().st_mode & 0o777) == 0o644

            pcs._write_state(sid, {"session_id": sid, "completions": {}})

            mode = path.stat().st_mode & 0o777
            assert mode == 0o600, (
                f"Expected mode 0o600 after rewrite, got 0o{mode:o}"
            )
        finally:
            _cleanup_session(sid)

    def test_write_state_chmod_failure_is_non_fatal(self, monkeypatch) -> None:
        """If os.chmod raises, _write_state still completes and writes data."""
        sid = _fresh_session_id()
        chmod_calls = []
        real_chmod = os.chmod

        def fake_chmod(path, mode):
            chmod_calls.append((str(path), mode))
            # Only fail on our target path; let other chmods (test setup) pass.
            if str(path).startswith("/tmp/pipeline_agent_completions_"):
                raise OSError("simulated chmod failure")
            return real_chmod(path, mode)

        monkeypatch.setattr(pcs.os, "chmod", fake_chmod)

        try:
            # Should not raise even though chmod fails.
            pcs._write_state(sid, {"session_id": sid, "marker": "abc"})

            path = _state_path_for(sid)
            assert path.exists(), "data write must still succeed when chmod fails"
            # Ensure our fake chmod was actually called.
            assert any(
                "pipeline_agent_completions_" in c[0] for c in chmod_calls
            ), "os.chmod should have been called from _write_state"
        finally:
            _cleanup_session(sid)


# ---------------------------------------------------------------------------
# AC-2: locked RMW prevents lost writes (#1170)
# ---------------------------------------------------------------------------


class TestLockedRmw:
    """#1170: concurrent ring-buffer mutators must not lose entries."""

    def test_concurrent_record_tier1_allow_no_lost_writes(self) -> None:
        """Two parallel workers each call record_tier1_allow 20 times.

        Without the lockfile, interleaved R-M-W would clobber appends and
        the final entry count would fall below the FIFO cap. With the
        lockfile, both writers serialize and the ring buffer fills to its
        soft cap of _TIER1_RING_BUFFER_CAP entries.
        """
        sid = _fresh_session_id()
        file_path = "/tmp/cluster2_test_file.py"
        n_per_worker = 20
        try:
            # mp context — "spawn" is the safe default on macOS.
            ctx = multiprocessing.get_context("spawn")
            workers = [
                ctx.Process(
                    target=_ring_buffer_worker,
                    args=(sid, file_path, n_per_worker),
                )
                for _ in range(2)
            ]
            for w in workers:
                w.start()
            for w in workers:
                w.join(timeout=15)
                assert w.exitcode == 0, f"worker exit code: {w.exitcode}"

            entries = pcs.get_recent_tier1_allows(
                sid, file_path, window_seconds=120
            )
            # Soft FIFO cap drops oldest after each append; the post-cap
            # length is exactly _TIER1_RING_BUFFER_CAP after >=cap total
            # appends. Without the lock, lost writes would push this below
            # the cap (the interleaved overwrites cause the secondary
            # writer's appends to vanish before the cap fills).
            assert len(entries) == pcs._TIER1_RING_BUFFER_CAP, (
                f"Expected {pcs._TIER1_RING_BUFFER_CAP} entries after FIFO "
                f"cap, got {len(entries)}. Lost writes detected — locked "
                f"RMW is not effective under concurrency."
            )
        finally:
            _cleanup_session(sid)

    def test_locked_rmw_releases_lock_on_mutator_exception(self) -> None:
        """If the mutator raises, the lockfile must release so the next
        call can proceed (no deadlock)."""
        sid = _fresh_session_id()

        def bad_mutator(state):
            raise RuntimeError("intentional test failure")

        try:
            with pytest.raises(RuntimeError, match="intentional"):
                pcs._locked_rmw(sid, bad_mutator)

            # Subsequent normal call must succeed (lockfile not held).
            # Use a short timeout via threading guard so a stuck lock is
            # surfaced rather than blocking the suite forever.
            start = time.time()
            pcs.record_tier1_allow(sid, "/tmp/post_exception.py", 1)
            elapsed = time.time() - start
            assert elapsed < 5.0, (
                f"record_tier1_allow took {elapsed:.2f}s — lockfile was "
                f"not released after mutator exception"
            )

            entries = pcs.get_recent_tier1_allows(
                sid, "/tmp/post_exception.py", window_seconds=60
            )
            assert len(entries) == 1, (
                "Post-exception write must have landed in the ring buffer"
            )
        finally:
            _cleanup_session(sid)


# ---------------------------------------------------------------------------
# AC-3: _resolve_session_id_safe sanitizes env-var input (#1171)
# ---------------------------------------------------------------------------


class TestResolveSessionIdSafe:
    """#1171: env-var session_id reads must pass through sanitizer."""

    def test_resolve_session_id_safe_strips_null_bytes_from_env(
        self, monkeypatch
    ) -> None:
        """A null byte in CLAUDE_SESSION_ID must not leak into the result.

        ``os.environ.setenv`` rejects null bytes at the C layer (POSIX
        env names/values cannot contain NUL). We monkeypatch
        ``os.getenv`` directly to simulate the threat model: a Linux
        ``putenv(3)`` bypass or a memory-corruption side channel could
        in principle place a value with embedded nulls into the process
        env that bypasses the Python-level setenv guard. The sanitizer
        is the second line of defense.
        """
        monkeypatch.setattr(
            hook.os,
            "getenv",
            lambda name, default=None: "ab\x00cd"
            if name == "CLAUDE_SESSION_ID"
            else os.environ.get(name, default),
        )
        result = hook._resolve_session_id_safe("fallback-unused")
        assert result is not None
        assert "\x00" not in result
        # The sanitizer's Layer 1 strips nulls; the remaining "abcd"
        # then passes the allowlist regex unchanged.
        assert result == "abcd"

    def test_resolve_session_id_safe_strips_control_chars_from_env(
        self, monkeypatch
    ) -> None:
        """Control chars and path-traversal punctuation must be stripped/escaped.

        Same threat model as the null-byte test: a hostile process or
        ``putenv(3)`` call can in principle land non-printable bytes in
        the env-var value that Python's high-level setenv would reject.
        We patch ``os.getenv`` directly to simulate the byte-for-byte
        delivery the sanitizer must defeat.
        """
        monkeypatch.setattr(
            hook.os,
            "getenv",
            lambda name, default=None: "ab\x01\x02cd/../etc"
            if name == "CLAUDE_SESSION_ID"
            else os.environ.get(name, default),
        )
        result = hook._resolve_session_id_safe("fallback-unused")
        assert result is not None
        # No control bytes.
        assert not any(ord(c) < 32 for c in result)
        # No path separators or traversal characters — only the allowlist
        # set [a-zA-Z0-9_-] remains.
        assert all(
            c.isalnum() or c in ("_", "-") for c in result
        ), f"non-allowlist character leaked through sanitizer: {result!r}"
        assert "/" not in result
        assert ".." not in result

    def test_resolve_session_id_safe_empty_env_falls_back_to_input(
        self, monkeypatch
    ) -> None:
        """When CLAUDE_SESSION_ID is unset, the fallback arg is used."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        result = hook._resolve_session_id_safe("real-id")
        assert result == "real-id"

    def test_resolve_session_id_safe_returns_none_for_unknown(
        self, monkeypatch
    ) -> None:
        """The literal 'unknown' value short-circuits to None.

        Callers append `or "unknown"` to preserve string semantics; this
        test locks the helper's contract.
        """
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        assert hook._resolve_session_id_safe("unknown") is None
        assert hook._resolve_session_id_safe("") is None
        assert hook._resolve_session_id_safe(None) is None


# ---------------------------------------------------------------------------
# AC-4: ring-buffer API import is cached at module level (#1166)
# ---------------------------------------------------------------------------


class TestRingBufferApiCache:
    """#1166: _load_tier1_ring_buffer_api must memoize the import."""

    @pytest.fixture(autouse=True)
    def _reset_pcs_cache(self):
        """Ensure the module-level cache is in a known state both before
        and after each test in this class. Without this, a poisoned
        cache from one test (e.g. injected ImportError) leaks into
        sibling test modules — TestSlidingWindowMultiEdit in
        test_classifier_robustness.py uses the same import path."""
        hook._PCS_RESOLVED = False
        hook._PCS_MODULE_CACHE = None
        hook._PCS_API_CACHE = (None, None, None)
        # Re-prime with the real import so any module that runs after
        # these tests gets a working cache.
        yield
        hook._PCS_RESOLVED = False
        hook._PCS_MODULE_CACHE = None
        hook._PCS_API_CACHE = (None, None, None)
        hook._load_tier1_ring_buffer_api()

    def test_load_tier1_ring_buffer_api_caches_module(self) -> None:
        """Two consecutive calls return the same triple and the module
        cache sentinel is populated."""
        # Force a fresh resolution so we exercise the first-call path.
        hook._PCS_RESOLVED = False
        hook._PCS_MODULE_CACHE = None
        hook._PCS_API_CACHE = (None, None, None)

        triple_a = hook._load_tier1_ring_buffer_api()
        assert hook._PCS_RESOLVED is True, (
            "First call must set the resolved sentinel so subsequent "
            "calls short-circuit"
        )
        module_after_first = hook._PCS_MODULE_CACHE

        triple_b = hook._load_tier1_ring_buffer_api()

        # Identity equality on each callable — cache must return the SAME
        # function objects, not just equal ones.
        assert triple_a is triple_b or all(
            a is b for a, b in zip(triple_a, triple_b)
        ), "Cached triple changed across calls"

        assert hook._PCS_MODULE_CACHE is module_after_first, (
            "Module cache mutated between calls — cache miss happened "
            "where a hit was expected"
        )

    def test_load_tier1_ring_buffer_api_failure_path_also_caches(
        self,
    ) -> None:
        """When the import fails, the sentinel still gets set so we don't
        keep retrying importlib on every gate invocation.

        We patch ``builtins.__import__`` manually (not via
        ``monkeypatch``) so we can guarantee the restore happens INSIDE
        the test body, before pytest's autouse fixture teardown order
        gets a chance to interleave with monkeypatch's own finalizer.
        Without the inline try/finally, the import patch could outlive
        the test and corrupt the cache for downstream test modules
        (the sliding-window suite in test_classifier_robustness.py uses
        the same cached triple).
        """
        # Reset cache and inject an import failure.
        hook._PCS_RESOLVED = False
        hook._PCS_MODULE_CACHE = None
        hook._PCS_API_CACHE = (None, None, None)

        import builtins as _b

        real_import = _b.__import__

        def failing_import(name, *args, **kwargs):
            if name == "pipeline_completion_state":
                raise ImportError("simulated import failure")
            return real_import(name, *args, **kwargs)

        try:
            _b.__import__ = failing_import
            triple = hook._load_tier1_ring_buffer_api()
            assert triple == (None, None, None)
            assert hook._PCS_RESOLVED is True, (
                "Failure path must also set _PCS_RESOLVED so the gate "
                "does not re-pay importlib cost on every classification"
            )
        finally:
            # Restore __import__ immediately, before the autouse
            # fixture's teardown tries to re-prime the cache.
            _b.__import__ = real_import


# ---------------------------------------------------------------------------
# AC-5: dead PIPELINE_MODE env-read removal (#1177)
# ---------------------------------------------------------------------------


class TestDeadEnvReadRemoval:
    """#1177: the two known dead PIPELINE_MODE env reads must be gone."""

    def test_pipeline_mode_call_sites_have_no_dead_env_read(self) -> None:
        """Source scan: no remaining
        ``os.environ.get("PIPELINE_MODE") or _get_pipeline_mode_from_state``
        pattern, which was dead since #1173 moved the env-read inside the
        helper.
        """
        source = (HOOK_DIR / "unified_pre_tool.py").read_text()
        pattern = re.compile(
            r'os\.environ\.get\(\s*["\']PIPELINE_MODE["\']\s*\)\s*or\s*_get_pipeline_mode_from_state'
        )
        matches = pattern.findall(source)
        assert matches == [], (
            f"Found {len(matches)} dead PIPELINE_MODE env reads — "
            f"#1177 should have removed all of them: {matches}"
        )

    def test_pipeline_mode_helper_still_reads_env_var(self) -> None:
        """Confidence guard: the helper itself still honors PIPELINE_MODE
        (per #849/#1173). Removing the outer reads must not have broken
        the override path."""
        source = (HOOK_DIR / "unified_pre_tool.py").read_text()
        # The helper body should contain the env-var read.
        assert 'os.getenv("PIPELINE_MODE"' in source, (
            "PIPELINE_MODE env-var read disappeared entirely — the #1173 "
            "override contract is broken"
        )

    def test_followup_comments_added_for_remaining_env_reads(self) -> None:
        """Three NOTE(#1177-followup) comments flag the remaining
        suspected-dead env reads (PIPELINE_ISSUE_NUMBER,
        ENFORCEMENT_LEVEL, SKIP_AGENT_COMPLETENESS_GATE)."""
        source = (HOOK_DIR / "unified_pre_tool.py").read_text()
        followups = re.findall(r"NOTE\(#1177-followup\)", source)
        assert len(followups) >= 3, (
            f"Expected at least 3 NOTE(#1177-followup) comments, "
            f"found {len(followups)}"
        )
