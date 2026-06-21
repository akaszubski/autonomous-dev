"""Regression tests for Issue #1193 — path traversal hardening in `verify_paths_exist`.

`plan_freshness.verify_paths_exist()` previously resolved relative paths via
``repo_root / candidate`` and called ``.exists()`` directly. A path containing
traversal segments (e.g. ``../../etc/passwd``) would therefore probe the
filesystem outside ``repo_root``. Severity is Low because the input is trusted
plan markdown, but the fix is cheap and removes a future-foot-gun.

The fix applies canonicalize-then-contain: resolve both ``candidate`` and
``repo_root``, then require the resolved candidate be a descendant of the
resolved root. Paths that escape are reported as missing — the helper never
checks ``.exists()`` outside ``repo_root``.

These tests pin the new behaviour and prevent regression. They use
``pytest``'s ``tmp_path`` fixture so each test runs in an isolated repo
root with no shared filesystem state.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from plan_freshness import verify_paths_exist  # noqa: E402


def test_relative_traversal_rejected(tmp_path: Path) -> None:
    """AC1: a relative path with leading traversal escapes `repo_root` and is reported missing.

    ``../../etc/passwd`` resolves to a path outside `tmp_path`. The helper
    must report it as missing regardless of whether ``/etc/passwd`` exists
    on the host filesystem — the point is that we never probe outside the
    repo root.
    """
    paths = ["../../etc/passwd"]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == ["../../etc/passwd"], (
        f"Traversal path must be reported as missing. Got {missing!r}"
    )


def test_embedded_traversal_rejected(tmp_path: Path) -> None:
    """AC2: traversal embedded mid-path (e.g. ``subdir/../../../sensitive.py``) is rejected.

    Even when the path starts with an innocuous-looking segment, the helper
    must canonicalize first and only accept paths that resolve INSIDE
    ``repo_root``. ``subdir/../../../sensitive.py`` resolves above ``tmp_path``.
    """
    paths = ["subdir/../../../sensitive.py"]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == ["subdir/../../../sensitive.py"], (
        f"Embedded traversal path must be reported as missing. Got {missing!r}"
    )


def test_legitimate_in_root_relative_path_resolves(tmp_path: Path) -> None:
    """AC3: a real file at a relative path inside `repo_root` is NOT reported missing.

    Regression guard: the hardening must not over-block. A genuine in-root
    relative path that exists on disk must still pass through cleanly.
    """
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "x.py").write_text("# real file")

    paths = ["lib/x.py"]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == [], (
        f"Legitimate in-root relative path must NOT be reported missing. "
        f"Got {missing!r}"
    )


def test_absolute_path_outside_repo_rejected(tmp_path: Path) -> None:
    """AC4: an absolute path outside `repo_root` is rejected regardless of host filesystem.

    The previous implementation called ``.exists()`` on absolute paths
    directly, exposing arbitrary filesystem probing. After hardening, an
    absolute path that is not a descendant of ``repo_root`` is treated as
    missing — we use a sibling of ``tmp_path`` to ensure the assertion is
    independent of whether ``/etc/passwd`` happens to exist on the host.
    """
    # Construct an absolute path that is guaranteed to be OUTSIDE tmp_path
    # but does live on the same filesystem so .resolve() works.
    outside = tmp_path.parent / "outside_target.py"
    # Do NOT create the file — the test asserts the helper rejects it for
    # being outside the root, not for being absent. (Creating it would still
    # produce the same expected outcome, but leaving it absent keeps the
    # intent crisp.)
    paths = [str(outside)]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == [str(outside)], (
        f"Absolute path outside repo_root must be reported missing. "
        f"Got {missing!r}"
    )


def test_legitimate_in_root_absolute_path_resolves(tmp_path: Path) -> None:
    """AC5: an absolute path pointing INSIDE `repo_root` to a real file is NOT missing.

    Regression guard for absolute-path handling: the helper must accept
    legitimate absolute paths that resolve within ``repo_root``.
    """
    (tmp_path / "real_inside.py").write_text("# real")
    inside = tmp_path / "real_inside.py"

    paths = [str(inside)]
    missing = verify_paths_exist(paths, tmp_path)
    assert missing == [], (
        f"Legitimate in-root absolute path must NOT be reported missing. "
        f"Got {missing!r}"
    )


def test_traversal_rejection_logged(tmp_path: Path, caplog) -> None:
    """Issue #1219: verify debug log is emitted when path traversal is rejected.

    When `verify_paths_exist` rejects a path for escaping repo_root via
    `relative_to()` raising ValueError, it should emit a debug log message
    containing the rejected path for incident investigation.
    """
    import logging
    
    # Enable debug logging for the plan_freshness module
    caplog.set_level(logging.DEBUG, logger="plan_freshness")
    
    # Use a path that will traverse outside repo_root
    traversal_path = "../../etc/passwd"
    missing = verify_paths_exist([traversal_path], tmp_path)
    
    # Behavior preserved: path is reported as missing
    assert traversal_path in missing, f"Path should be reported as missing, got {missing!r}"
    
    # Debug log should be emitted
    debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("traversal rejected" in msg.lower() for msg in debug_messages), (
        f"Expected 'traversal rejected' in debug logs, got: {debug_messages}"
    )
    # Verify the path is included in the debug message
    assert any(traversal_path in msg for msg in debug_messages), (
        f"Expected path '{traversal_path}' in debug logs, got: {debug_messages}"
    )
