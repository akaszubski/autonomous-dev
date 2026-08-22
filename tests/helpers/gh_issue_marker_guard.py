"""Leak guard for the gh-issue command-context marker (Issue #1609).

The marker is a global sanctioning file: whoever writes it tells the
``unified_pre_tool.py`` detectors that an issue-creating command is legitimately
in flight. A test that leaves it behind silently sanctions everything that runs
afterwards — Issue #1609 measured 49 tests in
``tests/unit/hooks/test_gh_issue_create_block.py`` flipping from "guard refuses"
to "guard permits" purely because ``tests/unit/lib`` had run first.

``tests/conftest.py`` removes the coupling by redirecting the marker path to a
per-run temp location before any test module is imported. This module is the
*second* line of defence: it snapshots the real path at session start, compares
at session finish, and fails the run if the state changed. That is what catches
offender number two — a future writer that reaches the real path some other way.

The comparison is a pure function so both arms (refuse a leak, permit a clean
run) can be observed directly, without a subprocess.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

__all__ = ["MarkerState", "snapshot_marker", "describe_marker_leak"]


@dataclass(frozen=True)
class MarkerState:
    """Observable state of the marker file at a point in time.

    Attributes:
        exists: Whether the path was present.
        mtime_ns: Modification time in nanoseconds, or ``None`` if absent.
        size: Size in bytes, or ``None`` if absent.
    """

    exists: bool
    mtime_ns: Optional[int] = None
    size: Optional[int] = None


def snapshot_marker(path: Union[str, Path]) -> MarkerState:
    """Capture the current state of the marker file.

    Args:
        path: Filesystem path to the marker.

    Returns:
        A :class:`MarkerState`. A path that cannot be stat'ed (missing, or
        unreadable directory) is reported as absent — the guard's job is to
        detect *change*, and an unreadable path that stays unreadable is no
        change.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return MarkerState(exists=False)
    return MarkerState(exists=True, mtime_ns=st.st_mtime_ns, size=st.st_size)


def describe_marker_leak(
    before: MarkerState,
    after: MarkerState,
    path: Union[str, Path],
) -> Optional[str]:
    """Compare two marker snapshots and describe any contamination.

    Three distinct forms of contamination are reported, because the requirement
    is that the real path ends the run *in whatever state it started in* — not
    merely that it ends absent:

    * created — the run wrote a marker that was not there before (the Issue
      #1609 defect: everything running afterwards is silently sanctioned);
    * modified — the run rewrote a marker a developer session owned (refreshing
      its mtime extends the 1-hour sanctioning TTL);
    * removed — the run deleted a marker a concurrent session was relying on.

    Args:
        before: State captured at session start.
        after: State captured at session finish.
        path: The path that was watched, for the message.

    Returns:
        A human-readable finding describing the leak, or ``None`` when the state
        is unchanged.
    """
    header = (
        "MARKER LEAK (Issue #1609): the global gh-issue command-context marker\n"
        f"  {path}\n"
    )
    remedy = (
        "\nEvery producer must resolve the path through "
        "gh_issue_context.gh_issue_context_path() (lib) or "
        "GH_ISSUE_COMMAND_CONTEXT_PATH (unified_pre_tool.py), both of which "
        "honour $GH_ISSUE_CMD_CONTEXT_PATH. tests/conftest.py redirects that "
        "variable, so a writer reaching the real path is bypassing the accessor."
    )

    if not before.exists and after.exists:
        return header + "was CREATED by this test run." + remedy
    if before.exists and not after.exists:
        return header + "was REMOVED by this test run." + remedy
    if before.exists and after.exists and (
        before.mtime_ns != after.mtime_ns or before.size != after.size
    ):
        return header + "was MODIFIED by this test run." + remedy
    return None


def watched_marker_path(default: Union[str, Path]) -> Path:
    """Resolve which path the session-level guard should watch.

    Normally the real, global marker path. ``AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH``
    redirects it so the guard's own meta-test can observe both arms in a child
    pytest session without touching the real file.

    Args:
        default: The real marker path to watch when no override is set.

    Returns:
        The path the guard should snapshot.
    """
    return Path(os.environ.get("AUTONOMOUS_DEV_TEST_CTX_WATCH_PATH") or default)
