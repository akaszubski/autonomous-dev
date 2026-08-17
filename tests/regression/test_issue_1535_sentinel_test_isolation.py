#!/usr/bin/env python3
"""Regression tests for Issue #1535: test runs must never touch the LIVE
protected-path authorization sentinel.

Running the unit suite armed ``<repo>/.claude/local/active_agent_dispatch.json``
— the file that ``unified_pre_tool.py``'s Issue #1296 gate consults to decide
whether a Write/Edit to ``agents/*.md``, ``commands/*.md``, ``hooks/*.py``,
``lib/*.py`` or ``skills/*/SKILL.md`` is coming from a dispatched agent. While
that test-armed sentinel is active the gate PERMITS a coordinator's direct edit
to protected infrastructure. The Issue #1448 sliding TTL means ordinary session
activity keeps refreshing it, so it survived far past the run that created it;
only the 4h ``MAX_LIFETIME_SECONDS`` ceiling hard-stopped it.

Two measured routes, one shared choke point:

  Route 1 (direct)   ``tests/unit/hooks/test_infrastructure_protection.py``
                     calls ``write("implementer")`` with no ``repo_root``.
  Route 2 (indirect) ``tests/unit/hooks/test_session_activity_logger.py``
                     contains no ``write()`` call at all — it drives
                     ``session_activity_logger.main()`` with a Task/Agent
                     ``PreToolUse`` payload and the HOOK calls ``write()``.

Route 2 is invisible to any grep of ``tests/`` for ``write(``, which is why the
fix is by construction (an autouse fixture intercepting the DEFAULT branch of
``agent_dispatch_sentinel._path``) rather than a call-site sweep. Both routes
funnel through ``_path()``, so one interception covers both — including any
future test that drives a hook with an Agent payload.

These tests are deliberately NON-DESTRUCTIVE even when they fail: each restores
the live sentinel's exact prior bytes (or its prior absence) before asserting,
so a RED run demonstrates the defect without causing it.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Iterator, Optional
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))
sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/hooks"))

import agent_dispatch_sentinel as ads  # noqa: E402
import session_activity_logger as sal  # noqa: E402

LIVE_SENTINEL = REPO_ROOT / ads._SENTINEL_REL


def _read_live() -> Optional[bytes]:
    """Return the live sentinel's exact bytes, or None if it is absent."""
    try:
        return LIVE_SENTINEL.read_bytes()
    except FileNotFoundError:
        return None


def _restore_live(payload: Optional[bytes]) -> None:
    """Put the live sentinel back exactly as it was (absent stays absent)."""
    if payload is None:
        with contextlib.suppress(FileNotFoundError, OSError):
            LIVE_SENTINEL.unlink()
        return
    LIVE_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    LIVE_SENTINEL.write_bytes(payload)


@contextlib.contextmanager
def _live_sentinel_guard() -> Iterator[dict]:
    """Record the live sentinel before/after the block, then restore it.

    Yields a dict that is populated with ``before`` and ``after`` byte payloads
    (``None`` for absent) once the block exits. Restoration happens in a
    ``finally`` so this helper never leaves the developer's real repo mutated —
    not even when the assertion that follows fails.
    """
    observed: dict = {}
    before = _read_live()
    try:
        yield observed
    finally:
        observed["before"] = before
        observed["after"] = _read_live()
        _restore_live(before)


def _describe(payload: Optional[bytes]) -> str:
    """Human-readable rendering of a sentinel payload for assertion messages."""
    return "<absent>" if payload is None else payload.decode("utf-8", "replace")


class TestIssue1535SentinelTestIsolation:
    """A test run must leave the live authorization sentinel byte-identical."""

    def test_default_path_branch_never_resolves_to_live_repo_sentinel(self) -> None:
        """``_path()`` (no-arg) must not point at the developer's real sentinel.

        This is the choke point. Every production caller — the writer in
        session_activity_logger, the reader in unified_pre_tool, the clearer in
        unified_session_tracker — uses this default branch.
        """
        resolved = ads._path()
        assert resolved != LIVE_SENTINEL, (
            "agent_dispatch_sentinel._path() resolves to the LIVE repo sentinel "
            f"({LIVE_SENTINEL}) during a test run. Any test that arms it grants "
            "the Issue #1296 gate a false 'agent dispatched' authorization for "
            "coordinator edits to protected infrastructure (Issue #1535)."
        )

    def test_route1_direct_write_leaves_live_sentinel_untouched(self) -> None:
        """Route 1: a bare ``write()`` must not mutate the live sentinel.

        Mirrors ``test_infrastructure_protection.py``'s ``_sentinel_write(
        "implementer")``. Note that its ``clear()`` cleanup is a no-op since
        Issue #1512 (an anonymous clear refuses unconditionally), so the armed
        sentinel outlives the test.
        """
        with _live_sentinel_guard() as obs:
            ads.write("issue-1535-probe")

        assert obs["after"] == obs["before"], (
            "agent_dispatch_sentinel.write() with no repo_root mutated the LIVE "
            f"sentinel.\n  before: {_describe(obs['before'])}\n"
            f"  after:  {_describe(obs['after'])}"
        )

    def test_route2_hook_driven_dispatch_leaves_live_sentinel_untouched(self) -> None:
        """Route 2: driving the hook with an Agent payload must not arm live.

        ``session_activity_logger.main()`` calls ``write()`` itself on a
        Task/Agent ``PreToolUse``. An empty ``subagent_type`` reproduces the
        measured artifact exactly (``agent: unknown``) while skipping the
        invocation-cache write, keeping this test scoped to the sentinel.
        """
        hook_input = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Task",
                "tool_input": {"description": "issue-1535 probe", "subagent_type": ""},
            }
        )

        with _live_sentinel_guard() as obs:
            with patch.dict(
                os.environ,
                {"ACTIVITY_LOGGING": "true", "CLAUDE_SESSION_ID": "issue-1535-route2"},
            ):
                with patch("sys.stdin", StringIO(hook_input)):
                    with pytest.raises(SystemExit):
                        sal.main()

        assert obs["after"] == obs["before"], (
            "session_activity_logger.main() armed the LIVE sentinel from a test. "
            "This route contains no write() call in the test file — the hook "
            "arms it — so a call-site sweep cannot fix it (Issue #1535).\n"
            f"  before: {_describe(obs['before'])}\n"
            f"  after:  {_describe(obs['after'])}"
        )

    def test_explicit_repo_root_branch_resolves_verbatim(self, tmp_path: Path) -> None:
        """The explicit-``repo_root`` branch must be preserved verbatim.

        The isolation fixture may only redirect the DEFAULT branch. Tests (and
        the 30+ existing ``repo_root=``-passing ones) must still get exactly the
        path they supplied, literal and un-normalized.
        """
        assert ads._path(tmp_path) == tmp_path / ads._SENTINEL_REL

        ads.write("explicit-branch", repo_root=tmp_path)
        expected = tmp_path / ads._SENTINEL_REL
        assert expected.exists(), "write(repo_root=...) must land at the given path"
        assert json.loads(expected.read_text())["agent"] == "explicit-branch"
        assert ads.is_active(repo_root=tmp_path) is True

    def test_writer_and_reader_converge_under_isolation(self) -> None:
        """NEGATIVE CONTROL: isolation must move writer and reader TOGETHER.

        ``test_infrastructure_protection.py`` writes the sentinel from the test
        and reads it back through ``hook.main()`` running in-process, both via
        the default branch. A fix that redirected only the test's write (e.g.
        passing ``repo_root=tmp_path`` at the call site) would decouple them and
        break ``test_install_manifest_allows_edit_inside_pipeline``. Isolating
        the shared ``_path()`` keeps them converged.
        """
        # Guarded like the others: this test writes through the DEFAULT branch
        # on purpose, so without the fixture it would clobber the live sentinel.
        # The guard keeps the whole file non-destructive in its RED state.
        with _live_sentinel_guard() as obs:
            ads.write("implementer")
            observed_active = ads.is_active()
            observed_path = ads._path()

        assert observed_active is True, (
            "A default-branch write() must be observable by a default-branch "
            "is_active(). Isolation that separates them has isolated the test "
            "from the hook instead of isolating both from the live repo."
        )
        assert observed_path.exists()
        assert obs["after"] == obs["before"], (
            "Convergence must be achieved in an isolated location, not by "
            "writing through to the live repo sentinel."
        )
