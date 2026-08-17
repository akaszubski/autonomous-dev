#!/usr/bin/env python3
"""Measure the phantom-vs-real SubagentStop split from the activity logs.

Issue #1512. A ``SubagentStop`` whose ``agent_transcript_path`` names a file
that was never written is not a dispatch completion. Before the fix, those
phantoms won the #1087 invocation cache (``duration_ms > 0``) and the genuine
completions missed it (``duration_ms == 0``) — 50/50 vs 52/52 over 102 typed
stops. This probe re-runs that measurement so the inversion can be confirmed
after deployment instead of asserted.

This is MEASUREMENT, never a gate: it always exits 0.

Controls printed alongside the main table, because every count in the original
investigation moved only when a control failed:

* **Retention** — a transcript can be absent because it was cleaned up, not
  because it never existed. The table is printed twice: over all records, and
  over only those records postdating the oldest surviving transcript in the
  referenced directories.
* **Basename disjointness** — if phantom and real transcript basenames overlap,
  the split is an artifact of retention rather than a real partition.
* **Word-count separation** — phantoms carry trivial output; real completions
  do not.

Usage:
    python3 scripts/measure_phantom_subagent_stops.py
    python3 scripts/measure_phantom_subagent_stops.py --since 2026-08-15
    python3 scripts/measure_phantom_subagent_stops.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_LOGS_DIR = ".claude/logs/activity"


def _load_typed_stops(logs_dir: Path, since: Optional[str]) -> List[Dict[str, Any]]:
    """Collect typed SubagentStop records from the activity logs.

    "Typed" means ``subagent_type`` is non-empty and not one of the internal
    ``__``-prefixed audit markers (``__dedup_skip__``, ``__phantom_stop__``,
    ``__unattributable__``, ...). That is the corpus the 102-event measurement
    used.

    Args:
        logs_dir: Directory containing ``*.jsonl`` activity logs.
        since: Optional ``YYYY-MM-DD`` lower bound applied to the log filename.

    Returns:
        List of parsed records, in file order.
    """
    records: List[Dict[str, Any]] = []
    for log_file in sorted(logs_dir.glob("*.jsonl")):
        if since and log_file.stem < since:
            continue
        try:
            handle = log_file.open()
        except OSError:
            continue
        with handle as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or rec.get("hook") != "SubagentStop":
                    continue
                agent = str(rec.get("subagent_type") or "")
                if not agent or agent.startswith("__"):
                    continue
                records.append(rec)
    return records


def _parse_timestamp(raw: Any) -> Optional[float]:
    """Best-effort ISO-8601 -> epoch seconds. Returns None on anything odd."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _retention_cutoff(records: List[Dict[str, Any]]) -> Optional[float]:
    """Oldest mtime among transcripts that still exist in referenced directories.

    Records older than this cutoff cannot be classified safely: their transcript
    may be absent because retention removed it.

    Args:
        records: Typed SubagentStop records.

    Returns:
        Epoch seconds of the oldest surviving transcript, or None if none exist.
    """
    parents = set()
    for rec in records:
        path = str(rec.get("agent_transcript_path") or "")
        if path:
            parents.add(Path(path).parent)
    mtimes: List[float] = []
    for parent in parents:
        try:
            for child in parent.glob("*.jsonl"):
                try:
                    mtimes.append(child.stat().st_mtime)
                except OSError:
                    continue
        except OSError:
            continue
    return min(mtimes) if mtimes else None


def _classify(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the phantom/real x hit/miss table plus the two extra controls.

    Args:
        records: Typed SubagentStop records to classify.

    Returns:
        Dict with the 2x2 counts, basename sets per class, and word-count ranges.
    """
    table: Counter = Counter()
    basenames: Dict[str, set] = {"phantom": set(), "real": set()}
    words: Dict[str, List[int]] = {"phantom": [], "real": []}

    for rec in records:
        raw_path = str(rec.get("agent_transcript_path") or "")
        if not raw_path:
            klass = "unknown"
        else:
            try:
                exists = Path(raw_path).exists()
            except OSError:
                exists = False
            klass = "real" if exists else "phantom"

        try:
            duration = float(rec.get("duration_ms") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        cache = "HIT" if duration > 0 else "MISS"
        table[(klass, cache)] += 1

        if klass in basenames and raw_path:
            basenames[klass].add(Path(raw_path).name)
            try:
                words[klass].append(int(rec.get("result_word_count") or 0))
            except (TypeError, ValueError):
                words[klass].append(0)

    return {"table": table, "basenames": basenames, "words": words}


def _format_table(title: str, result: Dict[str, Any]) -> str:
    """Render one classification result as a readable block."""
    table: Counter = result["table"]
    lines = [f"  {title}", "  " + "-" * 52]
    lines.append(f"  {'class':<10}{'cache HIT':>12}{'cache MISS':>12}{'total':>12}")
    total = 0
    for klass in ("phantom", "real", "unknown"):
        hit = table[(klass, "HIT")]
        miss = table[(klass, "MISS")]
        if hit == 0 and miss == 0:
            continue
        total += hit + miss
        lines.append(f"  {klass:<10}{hit:>12}{miss:>12}{hit + miss:>12}")
    lines.append(f"  {'TOTAL':<10}{'':>12}{'':>12}{total:>12}")

    phantom_names = result["basenames"]["phantom"]
    real_names = result["basenames"]["real"]
    shared = phantom_names & real_names
    lines.append("")
    lines.append(
        f"  control/basenames: {len(phantom_names)} phantom, {len(real_names)} real, "
        f"{len(shared)} shared (disjoint == 0 shared)"
    )
    for klass in ("phantom", "real"):
        counts = result["words"][klass]
        if counts:
            lines.append(
                f"  control/words[{klass}]: min={min(counts)} max={max(counts)} "
                f"n={len(counts)}"
            )
    return "\n".join(lines)


def main() -> int:
    """Print the phantom/real x hit/miss table. Always returns 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", default=None, help="YYYY-MM-DD lower bound on the log filename"
    )
    parser.add_argument("--logs-dir", default=DEFAULT_LOGS_DIR)
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="machine-readable output"
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    if not logs_dir.is_dir():
        print(
            f"No activity log directory at {logs_dir} — nothing to measure.",
            file=sys.stderr,
        )
        return 0  # measurement, never a gate

    records = _load_typed_stops(logs_dir, args.since)
    all_result = _classify(records)

    cutoff = _retention_cutoff(records)
    if cutoff is None:
        retained = records
    else:
        retained = [
            r for r in records if (_parse_timestamp(r.get("timestamp")) or 0) >= cutoff
        ]
    retained_result = _classify(retained)

    if args.as_json:
        payload = {
            "records": len(records),
            "retention_cutoff_epoch": cutoff,
            "all": {
                f"{k[0]}/{k[1]}": v for k, v in all_result["table"].items()
            },
            "retained": {
                f"{k[0]}/{k[1]}": v for k, v in retained_result["table"].items()
            },
            "retained_records": len(retained),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("Issue #1512 — phantom vs real SubagentStop (typed stops only)")
    print(f"logs: {logs_dir}   typed records: {len(records)}")
    print()
    print(_format_table("ALL RECORDS", all_result))
    print()
    if cutoff is None:
        print("  RETENTION CONTROL: no surviving transcripts found — cutoff N/A")
    else:
        stamp = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
        print(
            _format_table(
                f"POST-RETENTION-CUTOFF ({stamp}, {len(retained)} records)",
                retained_result,
            )
        )
    print()
    print(
        "Read the table in the direction that matters: before the #1512 fix the\n"
        "phantom row is all cache HIT and the real row is all cache MISS. After\n"
        "the fix that inverts — the real row takes the hits."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
