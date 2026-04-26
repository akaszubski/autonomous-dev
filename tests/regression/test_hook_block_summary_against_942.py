"""Regression: hook_block_summary reproduces #942 numbers ±5% (Issue #972 AC#4).

Reads the empirical numbers fixture extracted from the #942 issue body
and validates that ``scripts/hook_block_summary.py`` can produce
matching aggregate counts when fed a synthetic log file with the same
distribution.

If the fixture is in ``deferred`` state (no structured numbers were
extractable from #942 at implementation time), this test is skipped
with a clear reason — the AC then relaxes to a smoke check that the
script runs and exits 0 with non-empty output.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "hook_block_summary.py"
FIXTURE = REPO_ROOT / "tests" / "regression" / "fixtures" / "942_empirical_numbers.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def _row(*, ts: str, hook: str, reason: str) -> str:
    return json.dumps(
        {
            "ts": ts,
            "hook_name": hook,
            "reason": reason,
            "decision_shape": "tuple",
            "metadata": {},
            "session_id": "synthetic",
            "cwd": "/tmp",
        }
    )


def test_summary_reproduces_942_categories_within_tolerance(tmp_path):
    fixture = _load_fixture()
    if fixture.get("_status") == "deferred":
        pytest.skip(
            f"#942 numbers deferred: {fixture.get('_reason', 'no structured numbers')}"
        )

    tolerance_pct = float(fixture.get("_tolerance_pct", 5.0))
    categories = fixture["categories"]

    # Synthesise a log file with the empirical category distribution.
    # Each row gets a unique timestamp so the dedup logic in the summary
    # script (keyed on (ts, hook_name, reason)) does NOT collapse them.
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    log = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
    base_ts = datetime.now(timezone.utc)
    counter = 0

    def _ts() -> str:
        nonlocal counter
        counter += 1
        return (base_ts + timedelta(microseconds=counter)).isoformat()

    rows = []
    for n in range(categories["plan-exit"]):
        rows.append(
            _row(
                ts=_ts(),
                hook="plan_mode_exit_detector.py",
                reason="ExitPlanMode required",
            )
        )
    for n in range(categories["pipeline-state"]):
        rows.append(
            _row(
                ts=_ts(),
                hook="unified_pre_tool.py",
                reason="WORKFLOW ENFORCEMENT pipeline state required",
            )
        )
    for n in range(categories["agent-gates"]):
        rows.append(
            _row(ts=_ts(), hook="unified_pre_tool.py", reason="agent gate denied")
        )
    log.write_text("\n".join(rows) + "\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    for category, expected in categories.items():
        if expected == 0:
            continue
        actual = payload["by_category"].get(category, 0)
        delta = abs(actual - expected) / expected * 100
        assert delta <= tolerance_pct, (
            f"category {category}: expected {expected} ±{tolerance_pct}%, "
            f"got {actual} (delta={delta:.1f}%)"
        )


def test_summary_smoke_runs_against_empty_log(tmp_path):
    """AC#4 fallback: even when no fixture matches, the script must run cleanly."""
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.strip() != ""
