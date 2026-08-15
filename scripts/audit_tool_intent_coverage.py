#!/usr/bin/env python3
"""Audit tool_intent classifier coverage against observed tool calls.

CI gate per Issue #971 acceptance criterion #5: every distinct ``tool_name``
observed in the activity logs over the last N days MUST have a defined
classification (READ / WRITE / EXEC / known-EXEC).

If an unknown tool appears in the logs, this script flags it. The intent is
that whoever introduces a new tool also adds it to ``tool_intent.py`` (or to
the ``KNOWN_EXEC_TOOLS`` / ``MCP_KNOWN_EXEC_TOOLS`` sets here), so the
classifier never has to guess what an unrecognised tool does.

Issue #1503: MCP tools are no longer covered by a blanket ``mcp__`` prefix
match. That blanket declared every conceivable MCP tool covered by
construction, which is why this gate did not catch the serena editors walking
through the protected-infrastructure hard floor.

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
    # Messaging / orchestration primitives observed in the activity logs.
    # None of these touch the filesystem (Issue #1503 — they were reported
    # UNCOVERED once the blanket mcp__ pass was removed and the gate started
    # actually gating).
    "PushNotification", "RemoteTrigger", "SendMessage",
    "StructuredOutput", "Workflow",
}

# MCP tools that are valid non-file primitives — the MCP analogue of
# KNOWN_EXEC_TOOLS. Issue #1503: this script previously declared EVERY
# ``mcp__*`` name "covered" by construction (``if tool_name.startswith("mcp__"):
# return True``). That blanket is exactly why this CI gate never flagged the
# serena editors that were walking through the protected-infrastructure hard
# floor. An MCP tool is now covered only if it is in tool_intent's
# MCP_READ_TOOLS / MCP_WRITE_TOOLS registries, or explicitly listed here.
#
# Seeded from tools actually observed in .claude/logs/activity/.
MCP_KNOWN_EXEC_TOOLS: Set[str] = {
    # Web search / fetch
    "mcp__searxng__search", "mcp__searxng__fetch",
    # Microsoft 365
    "mcp__ms365__send-mail",
    # Home Assistant
    "mcp__home-assistant__ha_get_skill_guide",
    # Google Workspace bridge
    "mcp__hardened-workspace__get_events",
    "mcp__hardened-workspace__get_gmail_message_content",
    "mcp__hardened-workspace__get_gmail_messages_content_batch",
    "mcp__hardened-workspace__list_contacts",
    "mcp__hardened-workspace__search_gmail_messages",
    "mcp__hardened-workspace__start_google_auth",
    # Playwright — browser actions that are NOT read-only inspection
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    # HuggingFace / GitHub / misc integrations
    "mcp__github__create_issue",
    "mcp__claude_ai_PayPal__authenticate",
    "mcp__plugin_telegram_telegram__reply",
    # Obsidian
    "mcp__obsidian__search",
    # UniFi network
    "mcp__unifi-network__unifi_batch",
    "mcp__unifi-network__unifi_batch_status",
    "mcp__unifi-network__unifi_execute",
    "mcp__unifi-network__unifi_tool_index",
    # Test/fixture placeholder observed in the logs
    "mcp__custom__tool",
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
    # Issue #1503: explicit MCP registries, NOT a blanket mcp__ prefix pass.
    if tool_name in getattr(_tool_intent, "MCP_READ_TOOLS", frozenset()):
        return True
    if tool_name in getattr(_tool_intent, "MCP_WRITE_TOOLS", frozenset()):
        return True
    if tool_name in MCP_KNOWN_EXEC_TOOLS:
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
    # Issue #1503: mirrors _is_covered. The blanket ``startswith("mcp__")``
    # that used to live here reported every MCP tool as covered, so the
    # --print-classifications view agreed with a gate that was not checking
    # anything. Both helpers must apply the same registry test or the gate is
    # only half-fixed.
    if tool_name in getattr(_tool_intent, "MCP_READ_TOOLS", frozenset()):
        return "READ (mcp)"
    if tool_name in getattr(_tool_intent, "MCP_WRITE_TOOLS", frozenset()):
        return "WRITE (mcp)"
    if tool_name in MCP_KNOWN_EXEC_TOOLS:
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
            "(READ_TOOLS / WRITE_TOOLS / MCP_READ_TOOLS / MCP_WRITE_TOOLS), or "
            "to KNOWN_EXEC_TOOLS / MCP_KNOWN_EXEC_TOOLS in "
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
