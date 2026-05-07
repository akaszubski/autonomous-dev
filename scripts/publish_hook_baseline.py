#!/usr/bin/env python3
"""Publish hook timing baseline summary artifacts (Issue #1022, M1).

Reads a JSONL baseline file (produced by ``scripts/capture_baseline.py``)
and emits two derived artifacts next to it:

- ``<stem>.summary.json`` — aggregated stats with metadata block (machine-
  readable, diffable).
- ``<stem>.summary.md`` — human-readable report with Top-5 slowest hooks
  and Top-5 most-blocked gates tables.

Optionally cross-posts the report to a GitHub issue (off by default —
explicit ``--post`` opt-in). Cross-posting is idempotent via a sentinel
HTML comment marker; existing comments with the same sentinel are
PATCHed instead of appended.

Reuses ``scripts/hook_perf_report.py`` for aggregation. Does not modify
any input file.

Usage:

    # Default: dry-run, write JSON + Markdown summaries.
    python scripts/publish_hook_baseline.py \
        --jsonl baselines/2026-05-pre-refactor.jsonl

    # Cross-post to issue #943 (requires `gh` authenticated).
    python scripts/publish_hook_baseline.py \
        --jsonl baselines/2026-05-pre-refactor.jsonl \
        --post --issue 943

Exit codes:

    0  success
    1  IO error (missing JSONL, write failure)
    2  argparse / validation error
    3  gh CLI error (during --post)
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Reuse the W0 aggregator instead of recreating it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hook_perf_report import aggregate, stream_rows  # noqa: E402

# --- Constants ---------------------------------------------------------------

SCHEMA_VERSION = 1

# GitHub comment max body is 65_536 chars; reserve headroom for sentinel +
# truncation footer.
MAX_COMMENT_BODY_CHARS = 60_000

# Mirror the validation pattern used in lib/github_issue_closer.py.
MAX_ISSUE_NUMBER = 10_000_000

# Subprocess timeout for `gh` invocations.
GH_TIMEOUT_SECONDS = 15

# Sentinel label sanitization — only allow URL-safe chars.
SENTINEL_LABEL_RE = re.compile(r"^[A-Za-z0-9_:.\-]+$")

# Default issue if not specified for --post.
DEFAULT_ISSUE_NUMBER = 943

# Threshold that triggers a `synthetic-v0` data_kind classification.
# A real-workday capture should produce far more than this and span >1h.
SYNTHETIC_ROW_THRESHOLD = 500
SYNTHETIC_TIMESPAN_SECONDS = 3600  # 1 hour

# --- Metadata ----------------------------------------------------------------


def _git_short_sha() -> str:
    """Return short git SHA, or "unknown" if not in a repo or git missing."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "unknown"


def _platform_string() -> str:
    """Stable platform identifier (e.g. 'darwin-arm64', 'linux-x86_64')."""
    system = platform.system().lower()
    machine = platform.machine().lower() or "unknown"
    return f"{system}-{machine}"


def _classify_data_kind(row_count: int, ts_min: Optional[str], ts_max: Optional[str]) -> str:
    """Heuristic: synthetic-v0 if row_count low OR timespan too short.

    Args:
        row_count: Total rows in the JSONL.
        ts_min: ISO-8601 timestamp of earliest row, or None.
        ts_max: ISO-8601 timestamp of latest row, or None.

    Returns:
        ``"synthetic-v0"`` if either heuristic threshold is hit, else
        ``"real-workday"``.
    """
    if row_count < SYNTHETIC_ROW_THRESHOLD:
        return "synthetic-v0"
    if ts_min is None or ts_max is None:
        return "synthetic-v0"
    try:
        dt_min = _parse_iso(ts_min)
        dt_max = _parse_iso(ts_max)
    except ValueError:
        return "synthetic-v0"
    if (dt_max - dt_min).total_seconds() < SYNTHETIC_TIMESPAN_SECONDS:
        return "synthetic-v0"
    return "real-workday"


def _parse_iso(s: str) -> datetime:
    """Parse ISO-8601 with trailing 'Z' tolerance."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _scan_timestamps(jsonl_path: Path) -> tuple[int, Optional[str], Optional[str]]:
    """Single-pass scan: count rows + extract earliest/latest ts strings.

    Args:
        jsonl_path: Path to the source JSONL.

    Returns:
        ``(row_count, ts_min_iso, ts_max_iso)``. Either ts may be None
        if no rows have a parseable ``ts`` field.
    """
    row_count = 0
    ts_min: Optional[datetime] = None
    ts_max: Optional[datetime] = None
    ts_min_str: Optional[str] = None
    ts_max_str: Optional[str] = None

    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row_count += 1
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            ts_str = row.get("ts") if isinstance(row, dict) else None
            if not isinstance(ts_str, str):
                continue
            try:
                dt = _parse_iso(ts_str)
            except (ValueError, TypeError):
                continue
            if ts_min is None or dt < ts_min:
                ts_min = dt
                ts_min_str = ts_str
            if ts_max is None or dt > ts_max:
                ts_max = dt
                ts_max_str = ts_str
    return row_count, ts_min_str, ts_max_str


def build_metadata(jsonl_path: Path, *, schema_version: int = SCHEMA_VERSION) -> dict:
    """Build the metadata block for a baseline summary.

    Args:
        jsonl_path: Path to the source JSONL file.
        schema_version: Summary artifact schema version.

    Returns:
        Dict with: captured_at, generated_at, git_sha, platform,
        schema_version, source_jsonl, row_count, data_kind.

    Raises:
        FileNotFoundError: If ``jsonl_path`` does not exist.
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"baseline JSONL not found: {jsonl_path}")

    row_count, ts_min, ts_max = _scan_timestamps(jsonl_path)
    captured_at = ts_min if ts_min is not None else "unknown"
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data_kind = _classify_data_kind(row_count, ts_min, ts_max)

    # Express source_jsonl relative to repo root if possible; fall back to
    # the bare path string.
    source_jsonl_str = str(jsonl_path)
    try:
        repo_root = Path(__file__).resolve().parents[1]
        source_jsonl_str = str(jsonl_path.resolve().relative_to(repo_root))
    except ValueError:
        pass

    return {
        "captured_at": captured_at,
        "generated_at": generated_at,
        "git_sha": _git_short_sha(),
        "platform": _platform_string(),
        "schema_version": schema_version,
        "source_jsonl": source_jsonl_str,
        "row_count": row_count,
        "data_kind": data_kind,
    }


# --- Aggregation -------------------------------------------------------------


def aggregate_jsonl(jsonl_path: Path) -> dict:
    """Run ``aggregate`` over a JSONL file (full pass, no since filter)."""
    rows = stream_rows([jsonl_path], since=None)
    return aggregate(rows)


def build_summary_json(stats: dict, metadata: dict) -> dict:
    """Top-level summary JSON: ``{metadata, hooks}``."""
    return {"metadata": metadata, "hooks": stats}


# --- Markdown rendering ------------------------------------------------------


def _ms(ns: int) -> str:
    """Format nanoseconds as fixed-precision milliseconds."""
    try:
        return f"{int(ns) / 1_000_000:.3f}"
    except (TypeError, ValueError):
        return "0.000"


def _baseline_label(jsonl_path_str: str) -> str:
    """Strip directory + .jsonl extension to get a human-readable label."""
    name = Path(jsonl_path_str).name
    if name.endswith(".jsonl"):
        name = name[: -len(".jsonl")]
    return name


def _sentinel(label: str) -> str:
    """Build the idempotency sentinel comment for a baseline label."""
    return f"<!-- hook-timing-baseline:{label} -->"


def render_summary_markdown(stats: dict, metadata: dict, *, top: int = 5) -> str:
    """Render a human-readable Markdown report.

    Args:
        stats: Output of ``aggregate``.
        metadata: Output of ``build_metadata``.
        top: Number of rows to show in each ranking table.

    Returns:
        Markdown string.
    """
    label = _baseline_label(metadata.get("source_jsonl", "unknown"))
    sentinel = _sentinel(label)

    lines: list[str] = []
    lines.append(f"# Hook timing baseline — {label}")
    lines.append("")
    lines.append(sentinel)
    lines.append("")

    # Metadata table.
    lines.append("| Field            | Value                                  |")
    lines.append("| ---------------- | -------------------------------------- |")
    md_keys = [
        "captured_at",
        "generated_at",
        "git_sha",
        "platform",
        "schema_version",
        "source_jsonl",
        "row_count",
        "data_kind",
    ]
    for key in md_keys:
        val = metadata.get(key, "unknown")
        lines.append(f"| {key:<16} | {str(val):<38} |")
    lines.append("")

    # Methodology blockquote (only relevant for synthetic-v0 baselines).
    if metadata.get("data_kind") == "synthetic-v0":
        lines.append(
            "> **Methodology note**: This baseline was produced by "
            "`scripts/capture_baseline.py` (synthetic stdin payloads, "
            "~5 invocations × 24 hooks). It is a v0 reference for "
            "regression detection only — it is NOT a real-workday "
            "capture and does not satisfy AC1 of issue #1022. A "
            "real-workday refresh (≥4h active session, real tool "
            "traffic) is operational follow-up."
        )
        lines.append("")

    # Top-5 slowest hooks (by p95).
    lines.append("## Top-5 slowest hooks (by p95)")
    lines.append("")
    lines.append("| Hook | Count | p50 ms | p95 ms | p99 ms |")
    lines.append("|------|-------|--------|--------|--------|")
    by_p95 = sorted(stats.items(), key=lambda kv: kv[1].get("p95_ns", 0), reverse=True)[:top]
    if not by_p95:
        lines.append("| _(no data)_ | 0 | 0 | 0 | 0 |")
    else:
        for hook, s in by_p95:
            lines.append(
                f"| {hook} | {s.get('count', 0)} | "
                f"{_ms(s.get('p50_ns', 0))} | "
                f"{_ms(s.get('p95_ns', 0))} | "
                f"{_ms(s.get('p99_ns', 0))} |"
            )
    lines.append("")

    # Top-5 most-blocked gates (by block_ratio desc, tiebreak by block_count).
    lines.append("## Top-5 most-blocked gates (by block ratio)")
    lines.append("")
    lines.append("| Hook | Allow | Block | Block ratio |")
    lines.append("|------|-------|-------|-------------|")
    by_block = sorted(
        stats.items(),
        key=lambda kv: (kv[1].get("block_ratio", 0), kv[1].get("block_count", 0)),
        reverse=True,
    )[:top]
    # Always show the table — emit a placeholder row when there's nothing.
    has_any_block_signal = any(
        (s.get("block_count", 0) > 0 or s.get("allow_count", 0) > 0) for _, s in by_block
    )
    if not by_block or not has_any_block_signal:
        lines.append("| _(no allow/block signal in baseline)_ | 0 | 0 | 0.0000 |")
    else:
        for hook, s in by_block:
            lines.append(
                f"| {hook} | "
                f"{s.get('allow_count', 0)} | "
                f"{s.get('block_count', 0)} | "
                f"{s.get('block_ratio', 0):.4f} |"
            )
    lines.append("")

    # Baseline policy.
    lines.append("## Baseline policy")
    lines.append("")
    lines.append("Refresh triggers:")
    lines.append("")
    lines.append("- Before any change that may alter hook latency.")
    lines.append("- After a confirmed regression.")
    lines.append("- Quarterly, to track latency drift.")
    lines.append(
        "- **Pending**: Real-workday capture (#1022 AC1) — requires "
        "≥4h active session traffic."
    )
    lines.append("")

    # Source.
    raw = metadata.get("source_jsonl", "unknown")
    raw_filename = Path(raw).name
    summary_json_filename = raw_filename.replace(".jsonl", ".summary.json")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- Raw JSONL: [{raw}]({raw_filename})")
    lines.append(f"- Aggregated JSON: [{summary_json_filename}]({summary_json_filename})")
    lines.append(
        "- Generator: [scripts/publish_hook_baseline.py]"
        "(../scripts/publish_hook_baseline.py)"
    )
    lines.append("")

    return "\n".join(lines)


def render_issue_comment(
    stats: dict,
    metadata: dict,
    *,
    sentinel: str,
    artifact_url: Optional[str],
    top: int = 5,
) -> str:
    """Render the GitHub issue comment body.

    Truncates to ``MAX_COMMENT_BODY_CHARS`` with a footer pointing to the
    full artifact, since GitHub comment bodies are capped.

    Args:
        stats: Output of ``aggregate``.
        metadata: Output of ``build_metadata``.
        sentinel: Idempotency sentinel HTML comment.
        artifact_url: Optional URL to the full ``.summary.md`` for the
            "see full artifact" footer.
        top: Number of rows in each table.

    Returns:
        Comment body string, ≤ ``MAX_COMMENT_BODY_CHARS`` characters.
    """
    body = render_summary_markdown(stats, metadata, top=top)
    # The sentinel is already in the markdown; ensure it's preserved on
    # truncation (it MUST be in any posted body to keep idempotency).
    if sentinel not in body:
        body = sentinel + "\n\n" + body

    if len(body) <= MAX_COMMENT_BODY_CHARS:
        return body

    # Truncate. Keep header (sentinel + first 200 lines) and append a
    # truncation footer pointing to the full artifact if known.
    suffix_link = f" see {artifact_url}" if artifact_url else " see committed `.summary.md` artifact"
    footer = f"\n\n…(truncated, {len(body) - MAX_COMMENT_BODY_CHARS} chars omitted —{suffix_link})\n"
    cut_at = MAX_COMMENT_BODY_CHARS - len(footer)
    if cut_at <= 0:
        # Pathological — footer alone exceeds budget. Fall back to a
        # minimal truncation marker.
        return body[: MAX_COMMENT_BODY_CHARS - 3] + "..."
    return body[:cut_at] + footer


# --- Cross-post (gh CLI) -----------------------------------------------------


def _validate_issue_number(issue_number: int) -> None:
    """Mirror the validation in lib/github_issue_closer.py."""
    if not isinstance(issue_number, int) or issue_number <= 0:
        raise ValueError(f"Issue number must be positive integer (got: {issue_number!r})")
    if issue_number > MAX_ISSUE_NUMBER:
        raise ValueError(f"Issue number too large (max: {MAX_ISSUE_NUMBER})")


def _validate_sentinel_label(label: str) -> None:
    """Sentinel label must be URL-safe to avoid HTML/comment injection."""
    if not isinstance(label, str) or not label:
        raise ValueError(f"sentinel label must be non-empty string (got: {label!r})")
    if not SENTINEL_LABEL_RE.match(label):
        raise ValueError(
            f"sentinel label must match {SENTINEL_LABEL_RE.pattern} (got: {label!r})"
        )


def find_existing_comment(
    issue_number: int,
    sentinel: str,
    *,
    repo: Optional[str] = None,
) -> Optional[int]:
    """Return the comment id that contains ``sentinel``, or None.

    Uses ``gh api`` paginated listing. Subprocess invocation always uses
    list args with ``shell=False`` and a 15s timeout.

    Args:
        issue_number: Validated GitHub issue number.
        sentinel: Sentinel HTML comment to search for in comment bodies.
        repo: Optional ``OWNER/NAME`` override.

    Returns:
        Comment id (int), or None if not found / on error.
    """
    _validate_issue_number(issue_number)

    if repo is not None:
        endpoint = f"/repos/{repo}/issues/{issue_number}/comments"
    else:
        # Let `gh` resolve the repo from the cwd's git config.
        endpoint = f"repos/:owner/:repo/issues/{issue_number}/comments"

    cmd = ["gh", "api", "--paginate", endpoint]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            check=True,
            shell=False,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    try:
        comments = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(comments, list):
        return None

    for c in comments:
        if not isinstance(c, dict):
            continue
        body = c.get("body")
        if isinstance(body, str) and sentinel in body:
            cid = c.get("id")
            if isinstance(cid, int):
                return cid
    return None


def post_or_update_comment(
    issue_number: int,
    body: str,
    sentinel: str,
    *,
    repo: Optional[str] = None,
) -> int:
    """Idempotent post: PATCH if sentinel already present, else POST.

    Args:
        issue_number: Validated GitHub issue number.
        body: Already-rendered comment body (must include sentinel).
        sentinel: Idempotency sentinel.
        repo: Optional ``OWNER/NAME`` override.

    Returns:
        Comment id of the created or updated comment.

    Raises:
        RuntimeError: If gh CLI fails.
    """
    _validate_issue_number(issue_number)
    if sentinel not in body:
        raise ValueError("comment body must contain the sentinel marker")

    existing_id = find_existing_comment(issue_number, sentinel, repo=repo)

    if existing_id is not None:
        # PATCH — update in place.
        if repo is not None:
            endpoint = f"/repos/{repo}/issues/comments/{existing_id}"
        else:
            endpoint = f"repos/:owner/:repo/issues/comments/{existing_id}"
        cmd = [
            "gh",
            "api",
            "--method",
            "PATCH",
            endpoint,
            "-f",
            f"body={body}",
        ]
    else:
        # POST — create new.
        if repo is not None:
            endpoint = f"/repos/{repo}/issues/{issue_number}/comments"
        else:
            endpoint = f"repos/:owner/:repo/issues/{issue_number}/comments"
        cmd = [
            "gh",
            "api",
            "--method",
            "POST",
            endpoint,
            "-f",
            f"body={body}",
        ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            check=True,
            shell=False,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"gh CLI failed: {exc}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("gh CLI not found — install with `brew install gh`") from exc

    try:
        payload = json.loads(result.stdout)
        if isinstance(payload, dict) and isinstance(payload.get("id"), int):
            return payload["id"]
    except (json.JSONDecodeError, ValueError):
        pass
    return existing_id if existing_id is not None else 0


# --- CLI ---------------------------------------------------------------------


def _info(msg: str, *, quiet: bool, file=None) -> None:
    if quiet:
        return
    print(msg, file=file or sys.stderr)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="publish_hook_baseline.py",
        description="Publish hook timing baseline summary artifacts (Issue #1022).",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        required=True,
        help="Source JSONL baseline file.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Override output path for the summary JSON (default: <stem>.summary.json).",
    )
    parser.add_argument(
        "--summary-md",
        type=Path,
        default=None,
        help="Override output path for the summary Markdown (default: <stem>.summary.md).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Compute and print to stdout; write nothing to disk.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of rows to show in each table (default: 5).",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Cross-post to GitHub issue (default: dry-run only).",
    )
    parser.add_argument(
        "--issue",
        type=int,
        default=DEFAULT_ISSUE_NUMBER,
        help=f"Target GitHub issue number for --post (default: {DEFAULT_ISSUE_NUMBER}).",
    )
    parser.add_argument(
        "--sentinel-label",
        type=str,
        default=None,
        help="Override sentinel label (default: derived from JSONL filename).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Override gh CLI target repo (OWNER/NAME).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress info logging on stderr.",
    )

    args = parser.parse_args(argv)

    jsonl_path = args.jsonl
    if not jsonl_path.exists():
        print(f"error: JSONL file not found: {jsonl_path}", file=sys.stderr)
        return 1

    # Validate issue number early — even when --post is off, we accept the
    # value into argparse so we want to fail fast on absurd inputs.
    if args.post:
        try:
            _validate_issue_number(args.issue)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    # Build metadata + aggregate.
    try:
        metadata = build_metadata(jsonl_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    stats = aggregate_jsonl(jsonl_path)
    summary_json = build_summary_json(stats, metadata)
    summary_md = render_summary_markdown(stats, metadata, top=args.top)

    # Derive default output paths.
    stem = jsonl_path.with_suffix("").name  # strip .jsonl
    parent = jsonl_path.parent
    out_json = args.summary_json or (parent / f"{stem}.summary.json")
    out_md = args.summary_md or (parent / f"{stem}.summary.md")

    if args.no_write:
        print(json.dumps(summary_json, indent=2, sort_keys=True))
        print("---")
        print(summary_md)
    else:
        try:
            out_json.write_text(
                json.dumps(summary_json, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            out_md.write_text(summary_md, encoding="utf-8")
        except OSError as exc:
            print(f"error: failed to write summary artifacts: {exc}", file=sys.stderr)
            return 1
        _info(f"wrote {out_json}", quiet=args.quiet)
        _info(f"wrote {out_md}", quiet=args.quiet)

    # Cross-post (opt-in).
    if args.post:
        label = args.sentinel_label or _baseline_label(metadata.get("source_jsonl", stem))
        try:
            _validate_sentinel_label(label)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        sentinel = _sentinel(label)
        body = render_issue_comment(
            stats, metadata, sentinel=sentinel, artifact_url=None, top=args.top
        )
        try:
            cid = post_or_update_comment(args.issue, body, sentinel, repo=args.repo)
        except (RuntimeError, ValueError) as exc:
            print(f"error: gh CLI: {exc}", file=sys.stderr)
            return 3
        _info(f"posted/updated comment id={cid} on issue #{args.issue}", quiet=args.quiet)
    else:
        _info(
            "(dry-run; pass --post --issue N to cross-post)",
            quiet=args.quiet,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
