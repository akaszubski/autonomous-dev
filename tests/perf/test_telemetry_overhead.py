"""Telemetry overhead budget (Issue #1012, W0).

Measures the per-invocation overhead introduced by ``hook_timing.HookTimer``
relative to a no-op baseline. The performance contract for the W0 telemetry
surface is:

- p50 overhead ≤ +1 ms
- p99 overhead ≤ +5 ms

Methodology (paired alternating samples + gc.disable + median for p50):

1. Warm up the import + filesystem caches.
2. Record N=100 paired samples, alternating baseline / instrumented to
   minimize systematic timing drift.
3. Compute the per-sample overhead as ``instrumented - baseline``, then
   take the percentile of that paired-difference distribution.

The budget is for production-class hardware (Mac Studio M3 Ultra,
M4 Max). Shared CI runners are noisier; this test is therefore marked
``@pytest.mark.perf`` and excluded from default test runs.
"""

from __future__ import annotations

import gc
import statistics
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_timing  # noqa: E402

pytestmark = [pytest.mark.perf]


def _baseline() -> None:
    """No-op baseline that mirrors ``_instrumented`` minus the timer."""
    pass


def _instrumented(log_dir: Path) -> None:
    """Single HookTimer enter/exit cycle — the instrument under test."""
    with hook_timing.HookTimer("benchmark.py", log_dir=log_dir):
        pass


def _percentile(data: list[int], q: float) -> int:
    """Stdlib percentile via sorted+index (mirrors performance_profiler.py)."""
    if not data:
        return 0
    s = sorted(data)
    idx = int(len(s) * q)
    return s[min(idx, len(s) - 1)]


def test_timer_overhead_within_budget(tmp_path, monkeypatch):
    """HookTimer adds ≤ 1ms p50 / ≤ 5ms p99 vs a no-op baseline."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    log_dir = tmp_path / "timing_logs"

    # Warm-up: import paths, filesystem caches, JIT-friendly code paths.
    for _ in range(20):
        _baseline()
        _instrumented(log_dir)

    n = 100
    baseline_durs: list[int] = []
    instrumented_durs: list[int] = []

    gc.disable()
    try:
        for _ in range(n):
            t0 = time.perf_counter_ns()
            _baseline()
            baseline_durs.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            _instrumented(log_dir)
            instrumented_durs.append(time.perf_counter_ns() - t0)
    finally:
        gc.enable()

    overhead_p50_ns = (
        statistics.median(instrumented_durs) - statistics.median(baseline_durs)
    )
    overhead_p99_ns = _percentile(instrumented_durs, 0.99) - _percentile(
        baseline_durs, 0.99
    )

    overhead_p50_ms = overhead_p50_ns / 1_000_000
    overhead_p99_ms = overhead_p99_ns / 1_000_000

    # Surface measured numbers in test output for capture in PRs.
    print(f"\n[hook_timing overhead] p50={overhead_p50_ms:.3f}ms p99={overhead_p99_ms:.3f}ms")

    assert overhead_p50_ms <= 1.0, (
        f"p50 overhead {overhead_p50_ms:.3f}ms exceeds 1.0ms budget"
    )
    assert overhead_p99_ms <= 5.0, (
        f"p99 overhead {overhead_p99_ms:.3f}ms exceeds 5.0ms budget"
    )


def test_disabled_mode_overhead_is_negligible(tmp_path, monkeypatch):
    """When HOOK_TIMING_DISABLED=1, the timer fast-path adds ≤ 1ms p99."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv(hook_timing.DISABLE_ENV_VAR, "1")

    log_dir = tmp_path / "timing_logs"

    for _ in range(20):
        _baseline()
        _instrumented(log_dir)

    n = 100
    baseline_durs: list[int] = []
    instrumented_durs: list[int] = []

    gc.disable()
    try:
        for _ in range(n):
            t0 = time.perf_counter_ns()
            _baseline()
            baseline_durs.append(time.perf_counter_ns() - t0)

            t0 = time.perf_counter_ns()
            _instrumented(log_dir)
            instrumented_durs.append(time.perf_counter_ns() - t0)
    finally:
        gc.enable()

    overhead_p99_ns = _percentile(instrumented_durs, 0.99) - _percentile(
        baseline_durs, 0.99
    )
    overhead_p99_ms = overhead_p99_ns / 1_000_000

    print(f"\n[hook_timing disabled-mode overhead] p99={overhead_p99_ms:.3f}ms")
    assert overhead_p99_ms <= 1.0, (
        f"disabled-mode p99 overhead {overhead_p99_ms:.3f}ms exceeds 1.0ms"
    )
