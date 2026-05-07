"""Unit tests for ``scripts/hook_perf_report.py`` (Issue #1012, W0).

Covers:

- Percentile arithmetic matches sorted-index expectations.
- ``--json`` emits valid JSON.
- 10k-row synthetic input parses well under 5s.
- ``--last 1h`` filters by timestamp.
- ``--since ISO`` filters by timestamp.
- Empty / missing input → exit 0 with no error.
- ``allow``/``block`` counts and ratio are correct.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "hook_perf_report.py"


@pytest.fixture(scope="module")
def report_module():
    """Import the script as a module so we can call its functions directly."""
    spec = importlib.util.spec_from_file_location(
        "hook_perf_report", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_synthetic(
    path: Path,
    *,
    rows: int,
    hook: str = "auto_format.py",
    base_dur_ns: int = 1_000_000,
    base_ts: str = "2026-05-07T12:00:00+00:00",
    block_every: int = 3,
):
    """Write ``rows`` synthetic timing rows to ``path``."""
    with path.open("w") as fh:
        for i in range(rows):
            fh.write(
                json.dumps(
                    {
                        "ts": base_ts,
                        "hook": hook,
                        "dur_ns": (i + 1) * base_dur_ns,
                        "decision_shape": "tuple" if i % block_every == 0 else "allow",
                        "schema_version": 1,
                    }
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# Percentile arithmetic
# ---------------------------------------------------------------------------


class TestPercentileArithmetic:
    def test_percentiles_match_sorted_index(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=100)

        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))

        # Durations are 1, 2, 3, ..., 100 (in M-ns units).
        # Sorted index for p50: int(100 * 0.50) = 50 → durations[50] = 51M ns.
        # p95: int(100 * 0.95) = 95 → durations[95] = 96M ns.
        # p99: int(100 * 0.99) = 99 → durations[99] = 100M ns.
        s = stats["auto_format.py"]
        assert s["p50_ns"] == 51_000_000
        assert s["p95_ns"] == 96_000_000
        assert s["p99_ns"] == 100_000_000

    def test_single_row_is_its_own_percentile(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=1)
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        s = stats["auto_format.py"]
        assert s["p50_ns"] == 1_000_000
        assert s["p95_ns"] == 1_000_000
        assert s["p99_ns"] == 1_000_000


# ---------------------------------------------------------------------------
# Allow/block counts
# ---------------------------------------------------------------------------


class TestAllowBlockCounts:
    def test_allow_block_counts_correct(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=100, block_every=3)
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        s = stats["auto_format.py"]
        # i%3==0 → block. For i in 0..99: 34 such i (0,3,6,...,99).
        assert s["block_count"] == 34
        assert s["allow_count"] == 66
        assert s["block_ratio"] == 0.34

    def test_unknown_decision_shape_not_counted_as_block(
        self, report_module, tmp_path
    ):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        with log.open("w") as fh:
            for i in range(10):
                fh.write(
                    json.dumps(
                        {
                            "ts": "2026-05-07T12:00:00+00:00",
                            "hook": "x.py",
                            "dur_ns": 1,
                            "decision_shape": "exception",  # not in BLOCK_SHAPES
                            "schema_version": 1,
                        }
                    )
                    + "\n"
                )
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        s = stats["x.py"]
        assert s["allow_count"] == 0
        assert s["block_count"] == 0
        # No allow / no block → ratio defaults to 0/1 = 0.
        assert s["block_ratio"] == 0


# ---------------------------------------------------------------------------
# Performance budget
# ---------------------------------------------------------------------------


class TestPerformanceBudget:
    def test_10k_rows_parses_under_5s(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=10_000)

        start = time.perf_counter()
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"10k-row parse took {elapsed:.2f}s (>5s budget)"
        assert stats["auto_format.py"]["count"] == 10_000


# ---------------------------------------------------------------------------
# Time filters
# ---------------------------------------------------------------------------


class TestTimeFilters:
    def test_since_filters_old_rows(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        with log.open("w") as fh:
            # 5 rows: 3 old, 2 new.
            for ts in [
                "2026-05-01T00:00:00+00:00",
                "2026-05-02T00:00:00+00:00",
                "2026-05-03T00:00:00+00:00",
                "2026-05-08T00:00:00+00:00",
                "2026-05-09T00:00:00+00:00",
            ]:
                fh.write(
                    json.dumps(
                        {
                            "ts": ts,
                            "hook": "x.py",
                            "dur_ns": 1,
                            "decision_shape": "allow",
                            "schema_version": 1,
                        }
                    )
                    + "\n"
                )

        cutoff = datetime(2026, 5, 4, tzinfo=timezone.utc)
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(
            report_module.stream_rows(files, since=cutoff)
        )
        assert stats["x.py"]["count"] == 2

    def test_parse_relative_duration_supports_units(self, report_module):
        assert report_module.parse_relative_duration("1d") == timedelta(days=1)
        assert report_module.parse_relative_duration("6h") == timedelta(hours=6)
        assert report_module.parse_relative_duration("30m") == timedelta(minutes=30)
        assert report_module.parse_relative_duration("45s") == timedelta(seconds=45)
        assert report_module.parse_relative_duration("1d12h") == timedelta(
            days=1, hours=12
        )

    def test_parse_relative_duration_rejects_garbage(self, report_module):
        with pytest.raises(ValueError):
            report_module.parse_relative_duration("zzz")
        with pytest.raises(ValueError):
            report_module.parse_relative_duration("")
        with pytest.raises(ValueError):
            report_module.parse_relative_duration("3x")

    def test_parse_iso_ts_handles_z_suffix(self, report_module):
        dt = report_module.parse_iso_ts("2026-05-01T00:00:00Z")
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# CLI invocations (subprocess)
# ---------------------------------------------------------------------------


class TestCli:
    def test_json_output_is_valid(self, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=10)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(tmp_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        parsed = json.loads(result.stdout)
        assert "hooks" in parsed
        assert "auto_format.py" in parsed["hooks"]

    def test_text_output_includes_header_and_rows(self, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        _write_synthetic(log, rows=10)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "hook" in result.stdout
        assert "p50ms" in result.stdout
        assert "auto_format.py" in result.stdout

    def test_empty_dir_exit_zero(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # Either "(no rows)" text or empty JSON hooks.
        assert "(no rows)" in result.stdout or "no rows" in result.stdout.lower()

    def test_missing_dir_exit_zero(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(missing),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_invalid_last_exits_nonzero(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(tmp_path),
                "--last",
                "garbage",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert "error" in result.stderr.lower()

    def test_top_filter(self, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        with log.open("w") as fh:
            for hook_name in ["a.py", "b.py", "c.py", "d.py"]:
                for i in range(5):
                    fh.write(
                        json.dumps(
                            {
                                "ts": "2026-05-07T12:00:00+00:00",
                                "hook": hook_name,
                                "dur_ns": i * 1_000_000,
                                "decision_shape": "allow",
                                "schema_version": 1,
                            }
                        )
                        + "\n"
                    )
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--start-dir",
                str(tmp_path),
                "--top",
                "2",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # Only 2 hooks should appear in output.
        hook_count = sum(1 for h in ["a.py", "b.py", "c.py", "d.py"] if h in result.stdout)
        assert hook_count == 2


# ---------------------------------------------------------------------------
# Malformed input handling
# ---------------------------------------------------------------------------


class TestMalformedInput:
    def test_skips_invalid_json_lines(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        with log.open("w") as fh:
            fh.write("not json\n")
            fh.write(json.dumps(
                {"ts": "2026-05-07T12:00:00+00:00", "hook": "a.py", "dur_ns": 1,
                 "decision_shape": "allow", "schema_version": 1}
            ) + "\n")
            fh.write("{partial broken\n")
            fh.write(json.dumps(
                {"ts": "2026-05-07T12:00:00+00:00", "hook": "a.py", "dur_ns": 2,
                 "decision_shape": "allow", "schema_version": 1}
            ) + "\n")
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        assert stats["a.py"]["count"] == 2

    def test_skips_rows_missing_required_fields(self, report_module, tmp_path):
        log = tmp_path / "hook_timings_2026-05-07.jsonl"
        with log.open("w") as fh:
            # Missing 'hook' field.
            fh.write(json.dumps({"ts": "2026-05-07T12:00:00+00:00", "dur_ns": 1}) + "\n")
            # Valid row.
            fh.write(json.dumps(
                {"ts": "2026-05-07T12:00:00+00:00", "hook": "a.py", "dur_ns": 1,
                 "decision_shape": "allow", "schema_version": 1}
            ) + "\n")
        files = report_module.iter_log_files(start_dir=tmp_path)
        stats = report_module.aggregate(report_module.stream_rows(files))
        assert "a.py" in stats
        assert stats["a.py"]["count"] == 1
