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

# Issue #1611: this script had NO shape filter and reported every row in
# hook-blocks.jsonl as a block — including 574 Phase-E ``mode_skip`` rows,
# which record enforcement being SKIPPED. It ranked ``plan_mode_exit_detector``
# (a hook whose own docstring says it cannot block) fifth among blockers.
# The refusal vocabulary is imported from beside the writer rather than
# redefined here; a second copy is a second thing that can drift.
_LIB_DIR = Path(__file__).resolve().parent.parent / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

try:
    from hook_telemetry import (
        BLOCK_SHAPES,
        NON_REFUSAL_EVENT_TYPES,
        REFUSED_FIELD,
        is_refusal_row,
    )
except ImportError as exc:  # pragma: no cover — repo-local script
    raise ImportError(
        f"Cannot import the refusal vocabulary from hook_telemetry: {exc}\n"
        f"Expected: {_LIB_DIR / 'hook_telemetry.py'}\n"
        f"A local fallback copy is deliberately NOT provided — a second "
        f"definition is what Issue #1611 exists to remove.\n"
        f"See: plugins/autonomous-dev/lib/hook_telemetry.py"
    ) from exc

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
    normalized = {
        "ts": ts,
        "hook_name": hook_name,
        "reason": reason,
        "decision_shape": row.get("decision_shape", "legacy_recovery"),
        "metadata": row.get("metadata", {}),
        "session_id": row.get("session_id", ""),
        "cwd": row.get("cwd", ""),
    }
    # Issue #1611: classification is delegated to the ONE classifier beside the
    # writer. This function's only job is to present the row in the shape that
    # classifier expects — carrying the raw ``refused`` boolean across so
    # ``is_refusal_row`` can prefer it, and letting the legacy-schema default
    # above ("legacy_recovery") participate rather than being classified from a
    # missing field.
    #
    # It previously decided the boolean case itself, which read as a harmless
    # inlining of the same rule and was not: ``is_refusal_row`` also carves out
    # the recorder-written allows (NON_REFUSAL_EVENT_TYPES), and this copy did
    # not, so 57 ``prompt_integrity_recovery`` rows — allows — were counted here
    # as REFUSALS while the sibling reader forty lines away treated them as a
    # separate class. Deciding here at all is the defect; delegating is the fix.
    if isinstance(row.get(REFUSED_FIELD), bool):
        normalized[REFUSED_FIELD] = row[REFUSED_FIELD]
    normalized[REFUSED_FIELD] = is_refusal_row(normalized)
    return normalized


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
    """Aggregate events, keeping refusals and non-refusals separate (#1611).

    ``top_hooks`` ranks REFUSALS only, so a hook that cannot block can no
    longer appear in a blocker ranking. Non-refusal events are not dropped —
    they are counted, ranked and labelled under their own heading, because
    "enforcement was skipped, and why" is genuine signal. The defect was the
    channel silently merging the two, not the records themselves.

    "Refusal" is whatever :func:`hook_telemetry.is_refusal_row` says it is, and
    that is broader than the shape test the heading used to name: it also
    excludes the recorder-written allows (``prompt_integrity_recovery``). The
    heading asserts REFUSAL positively, so it must not be applied to rows known
    to be allows — 57 of them, in the live log, at the time this was written.

    Args:
        events: Normalized rows from :func:`collect_events`.
        top: How many hooks to list in each ranking.

    Returns:
        Summary dict. ``total_events`` remains the count of ALL rows read;
        ``refusals`` + ``non_refusal_events`` partition it exactly.
    """
    refusals = [e for e in events if e.get(REFUSED_FIELD)]
    non_refusals = [e for e in events if not e.get(REFUSED_FIELD)]

    by_hook = Counter(e["hook_name"] for e in refusals if e["hook_name"])
    by_hook_non_refusal = Counter(
        e["hook_name"] for e in non_refusals if e["hook_name"]
    )

    by_category: Counter = Counter()
    for e in refusals:
        by_category[_categorise(e["hook_name"], e["reason"])] += 1

    # Every event, refusal or not — an unknown future shape must be REPORTED
    # here rather than silently dropped. Fail visible, not closed.
    by_shape = Counter(
        e.get("decision_shape", "unknown") for e in events
    )

    return {
        "total_events": len(events),
        "refusals": len(refusals),
        "non_refusal_events": len(non_refusals),
        "refusal_shapes": sorted(BLOCK_SHAPES),
        "non_refusal_event_types": sorted(NON_REFUSAL_EVENT_TYPES),
        "top_hooks": by_hook.most_common(top),
        "top_non_refusal_hooks": by_hook_non_refusal.most_common(top),
        "by_category": dict(by_category),
        "by_decision_shape": dict(by_shape),
    }


def render_text(summary: Dict[str, Any], parse_errors: int) -> str:
    """Render the summary, labelling refusals and non-refusals separately."""
    out = []
    out.append(f"Hook block summary — {summary['total_events']} event(s) read")
    if parse_errors:
        out.append(f"  ({parse_errors} unparseable line(s) skipped)")
    out.append("")
    out.append(
        f"  {summary['refusals']:6d}  REFUSALS "
        f"(decision_shape in {', '.join(summary['refusal_shapes'])}, "
        f"excluding {', '.join(summary['non_refusal_event_types'])})"
    )
    out.append(
        f"  {summary['non_refusal_events']:6d}  NON-REFUSAL events "
        f"(mode_skip / allow / unknown shape, plus recorder-written allows "
        f"— enforcement did NOT refuse)"
    )
    out.append("")
    out.append("Top hooks by REFUSAL:")
    if not summary["top_hooks"]:
        out.append("  (none)")
    for hook, count in summary["top_hooks"]:
        out.append(f"  {count:6d}  {hook}")
    out.append("")
    out.append("Top hooks by NON-REFUSAL event (not blocks):")
    if not summary["top_non_refusal_hooks"]:
        out.append("  (none)")
    for hook, count in summary["top_non_refusal_hooks"]:
        out.append(f"  {count:6d}  {hook}")
    out.append("")
    out.append("By category (#942 buckets, REFUSALS only):")
    if not summary["by_category"]:
        out.append("  (none)")
    for cat, count in sorted(
        summary["by_category"].items(), key=lambda kv: -kv[1]
    ):
        out.append(f"  {count:6d}  {cat}")
    out.append("")
    out.append("By decision shape (ALL events):")
    for shape, count in sorted(
        summary["by_decision_shape"].items(), key=lambda kv: -kv[1]
    ):
        marker = "" if shape in BLOCK_SHAPES else "   <- not a refusal"
        out.append(f"  {count:6d}  {shape}{marker}")
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
