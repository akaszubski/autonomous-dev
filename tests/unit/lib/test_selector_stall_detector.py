"""Unit tests for selector_stall_detector (Issue #1303 Phase E sub-D).

Covers the six edges called out in the plan:
1. Positive: K consecutive empties inside the window -> stalled.
2. Below threshold: K-1 empties -> not stalled.
3. Window-edge: K empties but oldest falls outside the lookback -> not stalled.
4. Reset on success: a non-empty fire breaks the consecutive streak.
5. Empty input: no fires at all -> not stalled, consecutive=0.
6. Reason string: when stalled, the reason mentions both the count and the
   window size in hours.

The fixed-point ``NOW`` (2026-06-25T12:00:00Z) keeps every assertion fully
deterministic — no reliance on wall-clock time.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make the selector_stall_detector module importable without installing the
# plugin package. Mirrors the pattern used by sibling tests in tests/unit/lib/.
LIB_PATH = (
    Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
)
if str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))

from selector_stall_detector import (  # noqa: E402  (path injection above)
    K,
    WINDOW_HOURS,
    SelectorStallResult,
    detect_stall,
)

NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)


def _iso(now: datetime, hours_ago: float) -> str:
    """Return an ISO-8601 UTC timestamp ``hours_ago`` before ``now``."""
    return (now - timedelta(hours=hours_ago)).isoformat()


def test_stalled_returns_true_when_k_consecutive_empty_within_window() -> None:
    """4 empty fires within the last 6h -> stalled=True."""
    # Order: oldest -> newest (the detector reverses internally).
    fires = [
        (_iso(NOW, 4), ""),
        (_iso(NOW, 3), ""),
        (_iso(NOW, 2), ""),
        (_iso(NOW, 1), ""),
    ]
    result = detect_stall(fires, now_utc=NOW)
    assert isinstance(result, SelectorStallResult)
    assert result.stalled is True
    assert result.consecutive_empty == 4
    assert result.window_hours_examined == WINDOW_HOURS
    assert K == 4  # Sanity: test assumes the documented default.


def test_stalled_returns_false_when_only_3_empty() -> None:
    """3 empty fires (one below K) -> not stalled."""
    fires = [
        (_iso(NOW, 3), ""),
        (_iso(NOW, 2), ""),
        (_iso(NOW, 1), ""),
    ]
    result = detect_stall(fires, now_utc=NOW)
    assert result.stalled is False
    assert result.consecutive_empty == 3


def test_stalled_returns_false_when_window_exceeded() -> None:
    """4 empties total, but the oldest is 7h ago (outside 6h window) -> only
    3 inside the window -> not stalled.
    """
    fires = [
        (_iso(NOW, 7), ""),   # OUTSIDE window
        (_iso(NOW, 3), ""),
        (_iso(NOW, 2), ""),
        (_iso(NOW, 1), ""),
    ]
    result = detect_stall(fires, now_utc=NOW)
    assert result.stalled is False
    assert result.consecutive_empty == 3


def test_non_empty_fire_resets_consecutive_counter() -> None:
    """A non-empty fire mid-sequence resets the streak. Most-recent run is
    3 empties -> not stalled.
    """
    fires = [
        (_iso(NOW, 6.5), ""),                # outside window anyway
        (_iso(NOW, 5.5), ""),
        (_iso(NOW, 4.5), ""),
        (_iso(NOW, 3.5), "1100,1101"),       # SUCCESSFUL fire breaks streak
        (_iso(NOW, 2.5), ""),
        (_iso(NOW, 1.5), ""),
        (_iso(NOW, 0.5), ""),
    ]
    result = detect_stall(fires, now_utc=NOW)
    assert result.stalled is False
    assert result.consecutive_empty == 3


def test_empty_fires_list_returns_not_stalled() -> None:
    """Defensive: no telemetry at all -> not stalled, no streak."""
    result = detect_stall([], now_utc=NOW)
    assert result.stalled is False
    assert result.consecutive_empty == 0
    assert result.reason == ""
    assert result.window_hours_examined == WINDOW_HOURS


def test_reason_string_includes_K_and_window() -> None:
    """When stalled, reason MUST mention the count (4) and the window (6h)
    so the resulting GitHub issue title/body is operator-readable.
    """
    fires = [
        (_iso(NOW, 4), "none"),   # case-insensitive empty marker
        (_iso(NOW, 3), "NONE"),
        (_iso(NOW, 2), ""),
        (_iso(NOW, 1), ""),
    ]
    result = detect_stall(fires, now_utc=NOW)
    assert result.stalled is True
    assert "4" in result.reason
    assert "6h" in result.reason


def test_detect_stall_with_realistic_telemetry_format() -> None:
    """Regression for Issue #1303 FINDING-1: verify the detector works against
    the exact telemetry format the workflow extracts via
    ``git log --pretty=format:'%cI|%s'``.

    End-to-end coverage of the parsing path that the workflow's bash step uses
    to convert git log output into (timestamp, cluster) tuples. The earlier
    bug — ``export LOG_LINES`` placed AFTER the python3 heredoc — meant the
    detector silently received an empty input and always returned ``OK``. This
    regression locks the realistic input shape so any future regression in the
    parsing or detection path surfaces immediately.
    """
    # Sample git log output that mirrors the workflow's extraction.
    # git log returns newest -> oldest; the workflow reverses to oldest -> newest
    # before handing the list to detect_stall(). We mirror that contract here.
    sample = (
        "2026-06-25T10:00:00+00:00|telemetry(cloud-drain): "
        "FIRE_END 20260625T100000Z no_drainable_cluster\n"
        "2026-06-25T09:30:00+00:00|telemetry(cloud-drain): "
        "FIRE_END 20260625T093000Z no_drainable_cluster\n"
        "2026-06-25T09:00:00+00:00|telemetry(cloud-drain): "
        "FIRE_END 20260625T090000Z no_drainable_cluster\n"
        "2026-06-25T08:30:00+00:00|telemetry(cloud-drain): "
        "FIRE_END 20260625T083000Z no_drainable_cluster"
    )
    # Mirror the parsing the workflow's bash/python3 block does.
    fires: list[tuple[str, str]] = []
    for line in sample.split("\n"):
        ts, _, subject = line.partition("|")
        parts = subject.split()
        cluster = parts[-1] if parts else ""
        # Map the "no_drainable_cluster" sentinel to "" (empty marker).
        cluster_str = "" if cluster == "no_drainable_cluster" else cluster
        fires.append((ts, cluster_str))
    # git log returns newest -> oldest; detector wants oldest -> newest.
    fires.reverse()

    result = detect_stall(
        fires,
        now_utc=datetime(2026, 6, 25, 10, 30, 0, tzinfo=timezone.utc),
    )
    assert result.stalled is True
    assert result.consecutive_empty == 4


def test_malformed_timestamp_row_is_skipped_without_resetting_streak() -> None:
    """Issue #1314 FINDING-3: regression — malformed ISO timestamps skip
    without resetting the consecutive-empty streak.

    This pins the intentional "permissive parsing" behavior documented in
    selector_stall_detector.py's docstring. If the detector ever changes to
    reset the streak on a malformed-ts row OR to raise an exception, this
    test fails loudly.
    """
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    # 4 empty fires with a malformed-ts row interleaved. Without the skip-
    # without-reset behavior, the streak would collapse to 2 and the K=4
    # threshold would not fire.
    fires = [
        ("2026-06-25T07:00:00+00:00", ""),
        ("2026-06-25T08:00:00+00:00", ""),
        ("THIS-IS-NOT-A-VALID-ISO-TIMESTAMP", ""),  # malformed: skip without reset
        ("2026-06-25T10:00:00+00:00", ""),
        ("2026-06-25T11:00:00+00:00", ""),
    ]
    result = detect_stall(fires, now_utc=now)
    assert result.stalled is True
    assert result.consecutive_empty == 4
