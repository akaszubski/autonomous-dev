"""Coverage baseline storage and regression detection."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


def get_default_baseline_path() -> Path:
    """Resolve .claude/local/coverage_baseline.json from repo root, handling worktrees."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        git_path = parent / ".git"
        if git_path.is_dir() or git_path.is_file():
            return parent / ".claude" / "local" / "coverage_baseline.json"
    return cwd / ".claude" / "local" / "coverage_baseline.json"


def load_baseline(baseline_path: Optional[Path] = None) -> dict:
    """Load coverage baseline. Returns empty dict if missing or corrupted."""
    path = baseline_path or get_default_baseline_path()
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_baseline(
    coverage_pct: float,
    skip_count: int,
    total_tests: int,
    baseline_path: Optional[Path] = None,
) -> None:
    """Save coverage baseline."""
    path = baseline_path or get_default_baseline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "total_coverage": coverage_pct,
        "skip_count": skip_count,
        "total_tests": total_tests,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))


def check_coverage_regression(
    current_coverage: float,
    tolerance: float = 0.5,
    baseline_path: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Check if coverage regressed from baseline. Returns (passed, message)."""
    baseline = load_baseline(baseline_path)
    if not baseline or "total_coverage" not in baseline:
        return (True, f"Baseline established at {current_coverage:.1f}%")

    baseline_coverage = baseline["total_coverage"]
    threshold = baseline_coverage - tolerance

    if current_coverage >= threshold:
        return (True, f"Coverage maintained: {current_coverage:.1f}% (baseline: {baseline_coverage:.1f}%)")
    else:
        return (False, f"Coverage regression: {current_coverage:.1f}% < {baseline_coverage:.1f}% - {tolerance}% tolerance")


def check_skip_rate(skipped: int, total: int) -> Tuple[str, str]:
    """Check skip rate. Returns (level, message). Level is 'ok', 'warn', or 'block'."""
    if total == 0:
        return ("ok", "No tests found")
    rate = (skipped / total) * 100
    if rate <= 5.0:
        return ("ok", f"Skip rate {rate:.1f}% is acceptable")
    elif rate <= 10.0:
        return ("warn", f"Skip rate {rate:.1f}% exceeds 5% — consider fixing skipped tests")
    else:
        return ("block", f"Skip rate {rate:.1f}% exceeds 10% — must reduce skipped tests before proceeding")
