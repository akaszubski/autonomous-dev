#!/usr/bin/env python3
"""Triage script: per-hook block summary from hook-blocks.jsonl.

Reads ``.claude/logs/hook-blocks.jsonl`` (the unified telemetry log added
in Issue #972) AND, for one release cycle, the legacy
``.claude/logs/hook-recovery.jsonl`` (from Issue #970). Rows are
deduplicated by ``(timestamp, hook_name, reason)`` so re-running the
script after partial migration does not double-count.

Reproduces the per-category breakdown the #942 triage produced manually
by grepping session transcripts. Time-window filters (``--last 7d``,
``--since <ISO>``) match the empirical numbers in the #942 issue body.

Usage::

    python scripts/hook_block_summary.py
    python scripts/hook_block_summary.py --last 7d --top 10
    python scripts/hook_block_summary.py --since 2026-04-01 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_LOG_PATH = Path(".claude") / "logs" / "hook-blocks.jsonl"
LEGACY_LOG_PATH = Path(".claude") / "logs" / "hook-recovery.jsonl"

# Category buckets matching the #942 issue body breakdown.
CATEGORY_PATTERNS: List[Tuple[str, List[str]]] = [
    ("plan-exit", ["plan_mode_exit_detector", "PLAN", "plan-critic", "ExitPlan"]),
    ("pipeline-state", ["pipeline_state", "settings", "state file", "WORKFLOW ENFORCEMENT"]),
    ("agent-gates", ["agent", "spec-validator", "CIA", "doc-master"]),
    ("settings-write", ["settings.json", "settings-write"]),
]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Per-hook block summary from hook-blocks.jsonl",
    )
    p.add_argument(
        "--last",
        default=None,
        help="Time window relative to now, e.g. 7d, 24h, 30m. "
        "Mutually exclusive with --since.",
    )
    p.add_argument(
        "--since",
        default=None,
        help="ISO-8601 timestamp lower bound (e.g. 2026-04-01).",
    )
    p.add_argument(
        "--top",
        type=int,
        default=10,
        help="Show top N hooks by block count (default 10).",
    )
    p.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text table.",
    )
    p.add_argument(
        "--start-dir",
        default=None,
        help="Project root anchor (default cwd).",
    )
    return p.parse_args(argv)


def _parse_relative_window(spec: str) -> timedelta:
    """Parse '7d', '24h', '30m', '90s' into a timedelta."""
    m = re.fullmatch(r"(\d+)\s*([dhms])", spec.strip().lower())
    if not m:
        raise ValueError(
            f"Invalid --last value: {spec!r}\n"
            "Expected format: <integer><unit>, where unit is one of "
            "d (days), h (hours), m (minutes), s (seconds).\n"
            "Examples: 7d, 24h, 90m"
        )
    n, unit = int(m.group(1)), m.group(2)
    return {
        "d": timedelta(days=n),
        "h": timedelta(hours=n),
        "m": timedelta(minutes=n),
        "s": timedelta(seconds=n),
    }[unit]


def _resolve_lower_bound(
    last: Optional[str], since: Optional[str]
) -> Optional[datetime]:
    if last and since:
        raise ValueError("--last and --since are mutually exclusive")
    if last:
        delta = _parse_relative_window(last)
        return datetime.now(timezone.utc) - delta
    if since:
        # Accept bare date or full ISO with offset.
        try:
            dt = datetime.fromisoformat(since)
        except ValueError as exc:
            raise ValueError(f"Invalid --since value {since!r}: {exc}")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _read_jsonl_safely(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield parsed JSON rows from a JSONL file, skipping malformed lines.

    Treats parse errors as soft failures (increments a counter via the
    yielded sentinel ``{"_parse_error": True}``) so the summary script
    never crashes on corrupt log files.
    """
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    yield {"_parse_error": True}
                    continue
                if not isinstance(obj, dict):
                    yield {"_parse_error": True}
                    continue
                yield obj
    except OSError:
        return


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy and new schemas to a common shape.

    The new schema (``hook-blocks.jsonl``) uses ``ts`` and ``reason``.
    The legacy schema (``hook-recovery.jsonl``) uses ``timestamp`` and
    ``block_reason``. Both share ``hook_name``.
    """
    if "_parse_error" in row:
        return row
    ts = row.get("ts") or row.get("timestamp") or ""
    hook_name = row.get("hook_name") or ""
    reason = row.get("reason") or row.get("block_reason") or ""
    return {
        "ts": ts,
        "hook_name": hook_name,
        "reason": reason,
        "decision_shape": row.get("decision_shape", "legacy_recovery"),
        "metadata": row.get("metadata", {}),
        "session_id": row.get("session_id", ""),
        "cwd": row.get("cwd", ""),
    }


def _categorise(hook_name: str, reason: str) -> str:
    """Map (hook, reason) to one of the #942 category buckets."""
    haystack = f"{hook_name} {reason}".lower()
    for category, patterns in CATEGORY_PATTERNS:
        for pat in patterns:
            if pat.lower() in haystack:
                return category
    return "other"


def collect_events(
    *,
    start_dir: Optional[Path] = None,
    lower_bound: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Read both log paths, dedup, time-filter. Return (events, parse_errors)."""
    if start_dir is None:
        start_dir = Path.cwd()

    new_path = start_dir / DEFAULT_LOG_PATH
    legacy_path = start_dir / LEGACY_LOG_PATH

    seen: set = set()
    events: List[Dict[str, Any]] = []
    parse_errors = 0

    for source in (new_path, legacy_path):
        for raw in _read_jsonl_safely(source):
            if "_parse_error" in raw:
                parse_errors += 1
                continue
            row = _normalize_row(raw)
            key = (row["ts"], row["hook_name"], row["reason"])
            if key in seen:
                continue
            seen.add(key)

            if lower_bound is not None and row["ts"]:
                try:
                    row_dt = datetime.fromisoformat(row["ts"])
                    if row_dt.tzinfo is None:
                        row_dt = row_dt.replace(tzinfo=timezone.utc)
                    if row_dt < lower_bound:
                        continue
                except ValueError:
                    # Unparseable timestamp — include the row rather than drop.
                    pass

            events.append(row)

    return events, parse_errors


def summarise(events: List[Dict[str, Any]], top: int) -> Dict[str, Any]:
    by_hook = Counter(e["hook_name"] for e in events if e["hook_name"])
    by_category: Counter = Counter()
    for e in events:
        by_category[_categorise(e["hook_name"], e["reason"])] += 1

    by_shape = Counter(
        e.get("decision_shape", "unknown") for e in events
    )

    return {
        "total_events": len(events),
        "top_hooks": by_hook.most_common(top),
        "by_category": dict(by_category),
        "by_decision_shape": dict(by_shape),
    }


def render_text(summary: Dict[str, Any], parse_errors: int) -> str:
    out = []
    out.append(f"Hook block summary — {summary['total_events']} event(s)")
    if parse_errors:
        out.append(f"  ({parse_errors} unparseable line(s) skipped)")
    out.append("")
    out.append("Top hooks:")
    if not summary["top_hooks"]:
        out.append("  (none)")
    for hook, count in summary["top_hooks"]:
        out.append(f"  {count:6d}  {hook}")
    out.append("")
    out.append("By category (#942 buckets):")
    if not summary["by_category"]:
        out.append("  (none)")
    for cat, count in sorted(
        summary["by_category"].items(), key=lambda kv: -kv[1]
    ):
        out.append(f"  {count:6d}  {cat}")
    out.append("")
    out.append("By decision shape:")
    for shape, count in sorted(
        summary["by_decision_shape"].items(), key=lambda kv: -kv[1]
    ):
        out.append(f"  {count:6d}  {shape}")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        lower_bound = _resolve_lower_bound(args.last, args.since)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    start_dir = Path(args.start_dir) if args.start_dir else None
    events, parse_errors = collect_events(
        start_dir=start_dir, lower_bound=lower_bound
    )

    if not events:
        if args.output_json:
            print(json.dumps({"total_events": 0, "parse_errors": parse_errors}))
        else:
            print("No block events found in window.")
            if parse_errors:
                print(f"  ({parse_errors} unparseable line(s) skipped)")
        return 0

    summary = summarise(events, args.top)
    summary["parse_errors"] = parse_errors

    if args.output_json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(render_text(summary, parse_errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
