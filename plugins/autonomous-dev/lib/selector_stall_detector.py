"""Selector-stall detection for the drain-queue watchdog (Issue #1303 Phase E sub-D).

Backward-looking detector that consumes FIRE_END telemetry rows (timestamp +
cluster string) and reports whether the cloud-drain selector returned empty
for K consecutive fires within a lookback window. Used by
``.github/workflows/drain-watchdog.yml`` to file a ``selector-stall`` alert
issue when the autonomous loop has effectively halted.

Pure-Python. No I/O. No subprocess. Caller provides the fires list and
optionally injects ``now_utc`` for deterministic tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

# Stall thresholds — intentionally hardcoded per AC1 / Issue #1303 Finding 5.
# If tuning is later needed, edit here and add a regression test rather than
# exposing as workflow inputs (YAGNI).
K: int = 4              # consecutive empty fires that constitute a stall
WINDOW_HOURS: int = 6   # lookback window for counting fires


@dataclass(frozen=True)
class SelectorStallResult:
    """Outcome of a single ``detect_stall`` call.

    Attributes:
        stalled: True iff K or more consecutive empty fires were observed in
            the lookback window ending at ``now_utc``.
        consecutive_empty: Number of consecutive empty fires counted from the
            newest fire backward (capped at when the streak broke or the
            window edge was reached).
        window_hours_examined: The lookback window used (echoed back for
            traceability — matches the ``window_hours`` argument).
        reason: Human-readable summary, empty string when ``stalled`` is
            False.
    """

    stalled: bool
    consecutive_empty: int
    window_hours_examined: int
    reason: str


def detect_stall(
    fires: Sequence[tuple[str, str]],
    *,
    now_utc: datetime | None = None,
    k: int = K,
    window_hours: int = WINDOW_HOURS,
) -> SelectorStallResult:
    """Detect whether the watchdog produced K consecutive empty fires.

    Args:
        fires: Sequence of ``(timestamp_iso, cluster_str)`` tuples, ordered
            oldest -> newest. ``cluster_str`` is treated as empty when it is
            ``""`` or, case-insensitively, ``"none"``; any other value
            (e.g., ``"1100,1101"``, ``"no_drainable_cluster"`` callers should
            normalise upstream) counts as a non-empty fire.
        now_utc: Reference "now" timestamp. Defaults to
            ``datetime.now(timezone.utc)``. Injected for deterministic tests.
        k: Consecutive-empty threshold (default ``K=4``).
        window_hours: Lookback window in hours (default ``WINDOW_HOURS=6``).

    Returns:
        ``SelectorStallResult`` describing the stall status.

    Trust assumption (intentional, Issue #1314 LOW-2):
        Rows with malformed ISO timestamps are silently skipped without
        resetting the consecutive-empty streak. This is deliberate — the
        caller upstream produces these rows from ``git log %cI`` which is
        well-formed, so malformed timestamps indicate corrupted telemetry
        rather than legitimate state. Changing this to RESET the streak
        would convert any single corrupted commit subject into a stall
        detection-killer; changing it to RAISE would crash the watchdog
        on data corruption rather than degrade gracefully. See the
        regression test ``test_malformed_timestamp_row_is_skipped_without_resetting_streak``
        in ``tests/unit/lib/test_selector_stall_detector.py`` which pins this.

    Known limitation (AC4 relaxed, Issue #1303): v1 does NOT inspect cluster
    severities to suppress "all clusters severity=high" false positives. An
    operator may manually close such false-positive alerts. A follow-up issue
    should track extending the cluster_selector with skip-reasons.
    """
    if not fires:
        return SelectorStallResult(False, 0, window_hours, "")

    now = now_utc or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    # Count consecutive empty fires from the newest end, only those within
    # the window. Reset (break) on a non-empty fire or on a fire that falls
    # outside the window.
    consecutive = 0
    for ts_iso, cluster in reversed(fires):
        try:
            ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            # Malformed timestamp — skip without resetting the streak; the
            # caller produced this row, and we prefer to be permissive rather
            # than collapse the entire detection on one bad line.
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts <= cutoff:
            break  # fire is outside window — stop counting
        if cluster and cluster.strip().lower() not in ("", "none"):
            break  # non-empty fire — streak ends
        consecutive += 1

    if consecutive >= k:
        return SelectorStallResult(
            stalled=True,
            consecutive_empty=consecutive,
            window_hours_examined=window_hours,
            reason=(
                f"{consecutive} consecutive no_drainable_cluster fires in "
                f"last {window_hours}h"
            ),
        )
    return SelectorStallResult(False, consecutive, window_hours, "")
