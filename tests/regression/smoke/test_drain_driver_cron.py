"""Issue #1318: drain-driver cron tightening (5,35 instead of 5).

Pins the design decision to:
1. Use 5,35 (every 30 min at :05 and :35) instead of */30 (every 30 min at :00/:30)
2. Preserve the :05 offset from drain-watchdog's :00/:30 to avoid runner contention
"""
import re
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[3]  # tests/regression/smoke -> repo root
WORKFLOW_FILE = WORKTREE / ".github" / "workflows" / "drain-driver.yml"
WATCHDOG_FILE = WORKTREE / ".github" / "workflows" / "drain-watchdog.yml"


def test_drain_driver_cron_is_30_minute_cadence() -> None:
    """Issue #1318 — drain-driver should fire every 30 min, not hourly."""
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    # Look for the cron line — should match exactly `'5,35 * * * *'` (or equivalent)
    cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", content)
    assert cron_match, "cron line not found in drain-driver.yml"
    cron_expr = cron_match.group(1)
    assert cron_expr == "5,35 * * * *", \
        f"Expected drain-driver cron '5,35 * * * *', got {cron_expr!r}. Issue #1318."


def test_drain_driver_cron_does_not_collide_with_drain_watchdog() -> None:
    """Issue #1318 — drain-driver cron must NOT fire at :00 or :30 (drain-watchdog's slots)."""
    content = WORKFLOW_FILE.read_text(encoding="utf-8")
    cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", content)
    assert cron_match
    cron_expr = cron_match.group(1)
    # Extract minute field (first space-separated component)
    minute_field = cron_expr.split()[0]
    # Reject any cron that fires at :00 or :30 (drain-watchdog's slots per */30)
    # Acceptable: 5,35 / 5 / 4,34 / etc. Rejectable: 0,30 / 0,5 / 30 / */30
    minutes = []
    for piece in minute_field.split(","):
        if piece.startswith("*/"):
            step = int(piece[2:])
            minutes.extend(range(0, 60, step))
        else:
            minutes.append(int(piece))
    assert 0 not in minutes, f"drain-driver cron fires at :00 — collides with drain-watchdog (cron={cron_expr!r})"
    assert 30 not in minutes, f"drain-driver cron fires at :30 — collides with drain-watchdog (cron={cron_expr!r})"
