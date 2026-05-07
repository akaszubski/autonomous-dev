#!/usr/bin/env python3
"""Per-hook timing report (Issue #1012, W0).

Reads JSONL rows produced by ``hook_timing.HookTimer`` and prints
per-hook p50/p95/p99 latency plus per-(hook, decision_shape) allow/block
counts and ratio.

Usage:

    python scripts/hook_perf_report.py [--last 1d]
                                       [--since 2026-05-01T00:00:00Z]
                                       [--top 20]
                                       [--json]
                                       [--log-glob hook_timings_*.jsonl]
                                       [--start-dir PATH]

Performance contract:

- Streams JSONL line-by-line. No full-file load.
- ≤ 5s on a 10k-row file (typical 1-day production volume).
- Percentiles via stdlib sorted+index (no numpy dep).

The report consumer is the W0 baseline publisher (#1022) and human
operators inspecting hook latency. The script never modifies the input
files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

# Decision shapes that count as "block" outcomes for the allow/block ratio.
BLOCK_SHAPES = frozenset({"tuple", "dict", "exit2", "legacy_recovery"})


def _resolve_default_log_dir() -> Path:
    """Default to ~/.claude/logs (matches HookTimer write location)."""
    return Path.home() / ".claude" / "logs"


def parse_relative_duration(spec: str) -> timedelta:
    """Parse a relative time like ``1d``, ``6h``, ``30m``, ``45s``.

    Supports compound forms (e.g. ``1d12h``). Raises ValueError on
    malformed input.
    """
    if not spec:
        raise ValueError("empty duration spec")
    pattern = re.compile(r"(\d+)([dhms])")
    matches = pattern.findall(spec.strip())
    if not matches:
        raise ValueError(f"unrecognised duration spec: {spec!r}")
    consumed = "".join(n + u for n, u in matches)
    if consumed != spec.strip():
        raise ValueError(f"unrecognised duration spec: {spec!r}")
    total = timedelta()
    for n_str, unit in matches:
        n = int(n_str)
        if unit == "d":
            total += timedelta(days=n)
        elif unit == "h":
            total += timedelta(hours=n)
        elif unit == "m":
            total += timedelta(minutes=n)
        elif unit == "s":
            total += timedelta(seconds=n)
    return total


def parse_iso_ts(s: str) -> datetime:
    """Parse an ISO-8601 timestamp; trailing ``Z`` is treated as UTC."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iter_log_files(
    *,
    start_dir: Path,
    log_glob: str = "hook_timings_*.jsonl",
) -> list[Path]:
    """Return all JSONL files under ``start_dir`` matching ``log_glob``."""
    if not start_dir.exists():
        return []
    return sorted(start_dir.glob(log_glob))


def stream_rows(
    files: Iterable[Path],
    *,
    since: Optional[datetime] = None,
) -> Iterable[dict]:
    """Yield JSONL rows from ``files`` filtered by ``since``.

    Malformed rows are skipped silently (best-effort streaming).
    """
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if not isinstance(row, dict):
                        continue
                    if since is not None:
                        ts_str = row.get("ts")
                        if not isinstance(ts_str, str):
                            continue
                        try:
                            ts = parse_iso_ts(ts_str)
                        except (ValueError, TypeError):
                            continue
                        if ts < since:
                            continue
                    yield row
        except OSError:
            continue


def percentile(sorted_data: list[int], q: float) -> int:
    """Stdlib percentile via sorted+index. Mirrors performance_profiler.py."""
    if not sorted_data:
        return 0
    if len(sorted_data) == 1:
        return sorted_data[0]
    idx = int(len(sorted_data) * q)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def aggregate(rows: Iterable[dict]) -> dict[str, dict]:
    """Bucket durations + decision_shape counts per hook."""
    by_hook: dict[str, dict] = {}
    for row in rows:
        hook = row.get("hook")
        if not isinstance(hook, str):
            continue
        try:
            dur = int(row.get("dur_ns", 0))
        except (TypeError, ValueError):
            continue
        shape = row.get("decision_shape", "unknown")
        if not isinstance(shape, str):
            shape = "unknown"

        bucket = by_hook.setdefault(
            hook,
            {"durations": [], "shape_counts": {}, "allow": 0, "block": 0},
        )
        bucket["durations"].append(dur)
        bucket["shape_counts"][shape] = bucket["shape_counts"].get(shape, 0) + 1
        if shape == "allow":
            bucket["allow"] += 1
        elif shape in BLOCK_SHAPES:
            bucket["block"] += 1

    # Compute percentiles.
    result: dict[str, dict] = {}
    for hook, bucket in by_hook.items():
        durs = sorted(bucket["durations"])
        total = len(durs)
        allow = bucket["allow"]
        block = bucket["block"]
        denom = max(1, allow + block)
        result[hook] = {
            "count": total,
            "p50_ns": percentile(durs, 0.50),
            "p95_ns": percentile(durs, 0.95),
            "p99_ns": percentile(durs, 0.99),
            "allow_count": allow,
            "block_count": block,
            "block_ratio": round(block / denom, 4),
            "shape_counts": dict(sorted(bucket["shape_counts"].items())),
        }
    return result


def format_text_report(stats: dict[str, dict], *, top: int) -> str:
    """Sort by p95 desc and produce a fixed-width text table."""
    if not stats:
        return "(no rows)"

    rows = sorted(stats.items(), key=lambda kv: kv[1]["p95_ns"], reverse=True)[:top]
    lines = []
    header = (
        f"{'hook':<35}  {'count':>6}  {'p50ms':>7}  "
        f"{'p95ms':>7}  {'p99ms':>7}  {'allow':>6}  {'block':>6}  {'b_ratio':>7}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for hook, s in rows:
        lines.append(
            f"{hook:<35.35}  {s['count']:>6}  "
            f"{s['p50_ns'] / 1_000_000:>7.3f}  "
            f"{s['p95_ns'] / 1_000_000:>7.3f}  "
            f"{s['p99_ns'] / 1_000_000:>7.3f}  "
            f"{s['allow_count']:>6}  {s['block_count']:>6}  "
            f"{s['block_ratio']:>7.4f}"
        )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-hook timing report (Issue #1012, W0)",
    )
    parser.add_argument(
        "--last",
        help="Filter to events from the last N (e.g. 1d, 6h, 30m).",
    )
    parser.add_argument(
        "--since",
        help="Filter to events at or after this ISO-8601 timestamp.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Show the N hooks with highest p95 (default: 20).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text table.",
    )
    parser.add_argument(
        "--log-glob",
        default="hook_timings_*.jsonl",
        help="Glob pattern for log files (default: hook_timings_*.jsonl).",
    )
    parser.add_argument(
        "--start-dir",
        type=Path,
        default=None,
        help="Directory containing JSONL files (default: ~/.claude/logs).",
    )
    args = parser.parse_args(argv)

    start_dir = args.start_dir or _resolve_default_log_dir()

    since: Optional[datetime] = None
    if args.last:
        try:
            delta = parse_relative_duration(args.last)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        since = datetime.now(timezone.utc) - delta
    elif args.since:
        try:
            since = parse_iso_ts(args.since)
        except ValueError as exc:
            print(f"error: invalid --since: {exc}", file=sys.stderr)
            return 2

    files = iter_log_files(start_dir=start_dir, log_glob=args.log_glob)
    stats = aggregate(stream_rows(files, since=since))

    if args.json:
        print(json.dumps({"hooks": stats}, indent=2, sort_keys=True))
    else:
        print(format_text_report(stats, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
