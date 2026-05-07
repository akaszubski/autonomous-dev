"""Integration: pre-refactor timing baseline must exist and be parseable (Issue #1012, W0).

The baseline file is the "before" snapshot the W0 baseline publisher
(#1022) compares against. Without this artifact, regression detection
cannot work.

Guarantees:

1. The file exists at `baselines/2026-05-pre-refactor.jsonl`.
2. Contains ≥100 rows (≥5 invocations × 24 hooks ≈ 120 rows expected).
3. Every row is valid JSON and has all schema fields.
4. ``schema_version == 1`` for every row.
"""

from __future__ import annotations

import json
from pathlib import Path

# tests/integration/ → tests/ → repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "baselines" / "2026-05-pre-refactor.jsonl"

REQUIRED_FIELDS = {"ts", "hook", "dur_ns", "decision_shape", "schema_version"}


def test_baseline_file_exists():
    assert BASELINE.exists(), (
        f"missing baseline at {BASELINE}; "
        "run `python scripts/capture_baseline.py` to regenerate"
    )


def test_baseline_file_has_min_rows():
    """≥100 rows required by the W0 acceptance criteria."""
    rows = [
        line for line in BASELINE.read_text().splitlines() if line.strip()
    ]
    assert len(rows) >= 100, f"baseline has only {len(rows)} rows; need ≥100"


def test_every_row_is_valid_json_with_all_fields():
    """Every row parses and has the full schema."""
    bad_rows: list[str] = []
    for n, line in enumerate(BASELINE.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            bad_rows.append(f"line {n}: invalid JSON ({e})")
            continue
        if not isinstance(row, dict):
            bad_rows.append(f"line {n}: not a JSON object")
            continue
        missing = REQUIRED_FIELDS - set(row.keys())
        if missing:
            bad_rows.append(f"line {n}: missing fields {sorted(missing)}")
    assert not bad_rows, (
        f"baseline has {len(bad_rows)} malformed rows: {bad_rows[:5]}"
    )


def test_every_row_has_schema_version_1():
    for n, line in enumerate(BASELINE.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        assert row.get("schema_version") == 1, (
            f"line {n}: schema_version is {row.get('schema_version')!r}, expected 1"
        )


def test_dur_ns_is_int_in_every_row():
    for n, line in enumerate(BASELINE.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        assert isinstance(row["dur_ns"], int), (
            f"line {n}: dur_ns is {type(row['dur_ns']).__name__}, expected int"
        )
        assert row["dur_ns"] >= 0, f"line {n}: negative dur_ns"


def test_baseline_covers_multiple_hooks():
    """Baseline should cover at least most of the 24 active hooks."""
    hooks = set()
    for line in BASELINE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        hooks.add(row["hook"])
    # Allow some hooks to fail/timeout under synthetic stdin, but require
    # the bulk to be covered.
    assert len(hooks) >= 20, (
        f"baseline covers only {len(hooks)} unique hooks; expected ≥20 of 24"
    )
