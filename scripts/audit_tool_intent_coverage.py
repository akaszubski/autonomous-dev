#!/usr/bin/env python3
"""Audit tool_intent classifier coverage against observed tool calls.

CI gate per Issue #971 acceptance criterion #5: every distinct ``tool_name``
observed in the activity logs over the last N days MUST have a defined
classification (READ / WRITE / EXEC / known-EXEC / mcp__*).

If an unknown tool appears in the logs, this script flags it. The intent is
that whoever introduces a new native tool also adds it to ``tool_intent.py``
(or to the ``KNOWN_EXEC_TOOLS`` set here), so the classifier never has to
guess what an unrecognised tool does.

Usage:
    python scripts/audit_tool_intent_coverage.py
    python scripts/audit_tool_intent_coverage.py --days 7 --strict
    python scripts/audit_tool_intent_coverage.py --print-classifications
    python scripts/audit_tool_intent_coverage.py --logs-dir other/path

Exit codes:
    0 — all observed tools are covered (or --strict not set)
    1 — uncovered tools found and --strict was set

Importable as ``audit(logs_dir, days, strict=False)``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Tuple

# ---------------------------------------------------------------------------
# Defensive import of tool_intent — same loader pattern as the hook.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

_tool_intent = None
_ti_path = _LIB_DIR / "tool_intent.py"
if _ti_path.exists():
    _spec = importlib.util.spec_from_file_location("tool_intent", str(_ti_path))
    if _spec and _spec.loader:
        _tool_intent = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_tool_intent)


# Tools that are valid orchestration / non-file primitives. These are
# expected EXEC classifications; their absence from the READ/WRITE sets
# is intentional, not an oversight.
KNOWN_EXEC_TOOLS: Set[str] = {
    # Built-in non-file tools
    "Task", "WebFetch", "WebSearch",
    "TodoWrite", "ScheduleWakeup",
    "BashOutput", "KillShell",
    "SlashCommand",
    # Plan/worktree management
    "EnterPlanMode", "ExitPlanMode",
    "EnterWorktree", "ExitWorktree",
    # Cron / task scheduling primitives
    "CronCreate", "CronDelete", "CronList",
    "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop", "TaskUpdate",
    # Plugins & UI primitives
    "Skill", "Agent", "AgentOutputTool", "AskUserQuestion",
    "Monitor", "ToolSearch", "LSP",
}


def _is_covered(tool_name: str) -> bool:
    """Return True if a tool name has a defined classification."""
    if not tool_name or not isinstance(tool_name, str):
        return False
    if _tool_intent is None:
        return False
    if tool_name in _tool_intent.READ_TOOLS:
        return True
    if tool_name in _tool_intent.WRITE_TOOLS:
        return True
    if tool_name == "Bash":
        return True
    if tool_name in KNOWN_EXEC_TOOLS:
        return True
    if tool_name.startswith("mcp__"):
        return True
    return False


def _collect_tool_names(logs_dir: Path, days: int) -> Set[str]:
    """Walk JSONL activity logs for the last N days and collect tool names."""
    tools: Set[str] = set()
    if not logs_dir.exists():
        return tools

    cutoff = datetime.now() - timedelta(days=days)

    for f in sorted(logs_dir.glob("*.jsonl")):
        # Best-effort date filter from filename (YYYY-MM-DD.jsonl).
        try:
            stem = f.stem.split("-pipeline")[0]  # tolerate suffixed names
            file_date = datetime.strptime(stem, "%Y-%m-%d")
            if file_date < cutoff:
                continue
        except ValueError:
            # Unparseable filename — include to be safe.
            pass

        try:
            with f.open("r") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tn = entry.get("tool")
                    if isinstance(tn, str) and tn:
                        tools.add(tn)
        except OSError:
            continue

    return tools


def audit(
    logs_dir: Path,
    days: int = 30,
    *,
    strict: bool = False,
) -> Tuple[int, List[str]]:
    """Audit tool_intent coverage against the activity logs.

    Args:
        logs_dir: Path to ``.claude/logs/activity`` (or equivalent).
        days: Lookback window in days.
        strict: If True, return non-zero code when uncovered tools are found.

    Returns:
        Tuple of (exit_code, list_of_uncovered_tool_names). exit_code is 1
        in strict mode when uncovered tools are present, else 0.
    """
    if _tool_intent is None:
        # Module not loaded — cannot perform audit. Treat as failure.
        return (1 if strict else 0, ["__tool_intent_module_unavailable__"])

    tools = _collect_tool_names(logs_dir, days)
    uncovered = sorted(t for t in tools if not _is_covered(t))

    if uncovered and strict:
        return (1, uncovered)
    return (0, uncovered)


def _classify_summary(tool_name: str) -> str:
    """Return a one-word category for a tool (for --print-classifications)."""
    if _tool_intent is None:
        return "UNAVAILABLE"
    if tool_name in _tool_intent.READ_TOOLS:
        return "READ"
    if tool_name in _tool_intent.WRITE_TOOLS:
        return "WRITE"
    if tool_name == "Bash":
        return "BASH"
    if tool_name in KNOWN_EXEC_TOOLS:
        return "EXEC (known)"
    if tool_name.startswith("mcp__"):
        return "EXEC (mcp)"
    return "UNCOVERED"


def main(argv: List[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Audit tool_intent classifier coverage against activity logs."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window in days (default: 30).",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path(".claude/logs/activity"),
        help="Path to activity logs (default: .claude/logs/activity).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any uncovered tools are found.",
    )
    parser.add_argument(
        "--print-classifications",
        action="store_true",
        help="Print classification of every observed tool.",
    )
    args = parser.parse_args(argv)

    if _tool_intent is None:
        print(
            "ERROR: tool_intent module could not be loaded from "
            f"{_LIB_DIR / 'tool_intent.py'}. Audit cannot proceed.",
            file=sys.stderr,
        )
        return 1 if args.strict else 0

    exit_code, uncovered = audit(args.logs_dir, args.days, strict=args.strict)

    if args.print_classifications:
        all_tools = _collect_tool_names(args.logs_dir, args.days)
        for tool in sorted(all_tools):
            print(f"{_classify_summary(tool):>14}  {tool}")

    if uncovered:
        print(
            f"WARNING: {len(uncovered)} tool(s) observed in logs "
            f"have no tool_intent classification:",
            file=sys.stderr,
        )
        for t in uncovered:
            print(f"  - {t}", file=sys.stderr)
        print(
            "\nFix: add the tool to plugins/autonomous-dev/lib/tool_intent.py "
            "(READ_TOOLS / WRITE_TOOLS) or to KNOWN_EXEC_TOOLS in "
            "scripts/audit_tool_intent_coverage.py.",
            file=sys.stderr,
        )
    else:
        print(
            f"OK: all observed tools (last {args.days} days) are covered."
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
