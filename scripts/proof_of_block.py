#!/usr/bin/env python3
"""Proof-of-block: a guard is not enforcement until it has been watched
refusing something. (Issue #1520)

WHY THIS EXISTS
---------------
Unit tests prove a function runs. They do not prove a guard is registered,
reachable, loaded from the copy production uses, or capable of refusing
anything. Measured in one session:

  - 5 of 6 block-capable hooks in a consumer repo had never emitted a block in
    3.5 months, with green tests throughout
  - plan_gate failed OPEN for every MCP editing tool (#1503); its tests passed
    because they only covered enumerated tools
  - a fixed function's production call site passed different arguments, so the
    fixed branch could never execute
  - three merged fixes were absent from the deployed copies that actually run

Every one of those is invisible to a log reader, because a guard that never
fires produces no logs. This harness stops waiting to OBSERVE enforcement and
instead DEMANDS that each guard refuse something on command.

THE CONTRACT
------------
Each guard declares two scenarios:

  positive  - a realistic action it MUST refuse
  negative  - the closest legitimate action it MUST allow

Both are required. A guard that blocks everything is as broken as one that
blocks nothing, and only the pair distinguishes them. A guard with no current
proof is reported UNVERIFIED and must not be counted as enforcement.

Hooks are driven END-TO-END as subprocesses with real payloads on stdin and
real decision JSON parsed from stdout -- the same path Claude Code uses -- so
"registered but unreachable" and "fixed but not wired" both surface.

USAGE
-----
    python3 proof_of_block.py            # replay, exit 1 on any failure
    python3 proof_of_block.py --record   # write artifacts
    python3 proof_of_block.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "plugins" / "autonomous-dev" / "hooks"
ARTIFACTS = REPO / "tests" / "proofs"

BLOCKED = {"deny", "block", "ask"}


# --------------------------------------------------------------------------
# scenario fixtures
# --------------------------------------------------------------------------

def _adev_repo(root: Path) -> Path:
    """A directory that repo_detector recognises as autonomous-dev.

    Requires BOTH a .git directory AND a marketplace.json whose CONTENT
    contains the string "autonomous-dev". Learned the hard way: an empty
    ``{}`` passes the exists() check, fails the content check, and silently
    reproduces nothing -- a fixture that cannot observe the behaviour it names.
    """
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "."], cwd=str(root),
                   capture_output=True, check=False)
    md = root / "plugins" / "autonomous-dev" / ".claude-plugin"
    md.mkdir(parents=True, exist_ok=True)
    (md / "marketplace.json").write_text('{"name": "autonomous-dev"}')
    (root / "plugins" / "autonomous-dev" / "lib").mkdir(parents=True, exist_ok=True)
    return root


def _plan_exited(root: Path) -> Path:
    """An autonomous-dev repo sitting at the plan_exited stage."""
    _adev_repo(root)
    (root / ".claude" / "plan_mode_exit.json").write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "proof-of-block",
        "stage": "plan_exited",
    }))
    return root


def _real_repo(root: Path) -> Path:
    """Use the REAL repo as the target, ignoring the temp dir.

    Required for guards whose scoping keys off the canonical autonomous-dev
    source. A synthetic temp repo does NOT trigger canonical-source detection,
    so the guard correctly declines to fire there -- and a harness using a temp
    fixture reports a false FAILS-OPEN.

    This is safe: PreToolUse only RETURNS a decision. The hook never performs
    the tool call, so pointing at real protected paths mutates nothing. Both
    scenarios below are decision-only.

    Caught by comparing against a control that ran the same payload against the
    real repo and got `deny` -- the first draft of this harness reported two
    false FAILS-OPEN before that comparison.
    """
    return REPO


# --------------------------------------------------------------------------
# the guard registry
# --------------------------------------------------------------------------
# Each entry: positive (must refuse) + negative control (must permit).

GUARDS = [
    {
        "guard": "protected-infrastructure-hard-floor",
        "issue": "#1435",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "direct Write to a protected lib path must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "plugins/autonomous-dev/lib/pipeline_state.py"),
                "content": "x = 1\n"},
        },
        "negative": {
            "why": "an ordinary docs write must NOT be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "docs" / "notes.md"),
                "content": "# notes\n"},
        },
    },
    {
        "guard": "mcp-write-classification",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "an MCP editor must be refused on a protected path, "
                   "classified by EFFECT not by tool name",
            "tool_name": "mcp__serena__replace_content",
            "tool_input": lambda r: {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "needle": "a", "repl": "b", "mode": "literal"},
        },
        "negative": {
            "why": "a read-only MCP tool must NOT be refused",
            "tool_name": "mcp__serena__find_symbol",
            "tool_input": lambda r: {"name_path": "foo"},
        },
    },
    {
        "guard": "plan-exit-gate",
        "issue": "#926/#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "at plan_exited an MCP writer must be refused",
            "tool_name": "mcp__serena__replace_content",
            "tool_input": lambda r: {
                "relative_path": "src/a.py", "needle": "a",
                "repl": "b", "mode": "literal"},
        },
        "negative": {
            "why": "at plan_exited the mandated search path must still work; "
                   "reading is not acting",
            "tool_name": "mcp__searxng__search",
            "tool_input": lambda r: {"query": "python"},
        },
    },
    {
        # I hit this one myself today: it correctly refused a new script.
        "guard": "write-pipeline-gate",
        "issue": "#1142",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "creating a NEW production code file outside the pipeline "
                   "must be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "scripts" / "pob_probe_newfile.py"),
                "content": "print('x')\n"},
        },
        "negative": {
            "why": "a markdown doc must NOT be refused",
            "tool_name": "Write",
            "tool_input": lambda r: {
                "file_path": str(r / "docs" / "pob_probe_note.md"),
                "content": "# note\n"},
        },
    },
    {
        "guard": "mcp-rename-symbol-is-a-write",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _real_repo,
        "positive": {
            "why": "rename_symbol mutates files and must be classified as a "
                   "write even though its name contains no write verb",
            "tool_name": "mcp__serena__rename_symbol",
            "tool_input": lambda r: {
                "relative_path": "plugins/autonomous-dev/lib/pipeline_state.py",
                "name_path": "save_pipeline", "new_name": "x"},
        },
        "negative": {
            "why": "get_symbols_overview only reads",
            "tool_name": "mcp__serena__get_symbols_overview",
            "tool_input": lambda r: {"relative_path": "README.md"},
        },
    },
    {
        "guard": "mcp-side-effect-set",
        "issue": "#1503 AC#19",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "browser_evaluate executes arbitrary JS and carries NO path "
                   "or content argument, so no shape test can catch it -- it "
                   "must be caught by the explicit side-effect set",
            "tool_name": "mcp__playwright__browser_evaluate",
            "tool_input": lambda r: {"function": "() => document.title"},
        },
        "negative": {
            "why": "browser_snapshot only observes",
            "tool_name": "mcp__playwright__browser_snapshot",
            "tool_input": lambda r: {},
        },
    },
    {
        "guard": "unenumerated-mcp-writer-by-shape",
        "issue": "#1503",
        "hook": "unified_pre_tool.py",
        "fixture": _plan_exited,
        "positive": {
            "why": "a tool from a server nobody enumerated, carrying a path "
                   "AND content, must be refused BY SHAPE -- this is the whole "
                   "point of classifying by effect rather than by name",
            "tool_name": "mcp__someserver__apply_patch",
            "tool_input": lambda r: {
                "relative_path": "src/a.py", "content": "x = 1\n"},
        },
        "negative": {
            "why": "the same unknown server's read tool must NOT be refused",
            "tool_name": "mcp__someserver__list_things",
            "tool_input": lambda r: {"query": "x"},
        },
    },
]


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

def drive(hook: Path, tool_name: str, tool_input: dict, cwd: Path) -> tuple:
    """Run the hook the way Claude Code does. Returns (decision, reason)."""
    payload = {
        "session_id": "proof-of-block",
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    for k in ("AUTONOMOUS_DEV_BYPASS", "ENFORCEMENT_LEVEL", "SKIP_PLAN_CHECK",
              "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=120,
                       cwd=str(cwd), env=env)
    decision, reason = "allow", ""
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        hso = d.get("hookSpecificOutput", {})
        decision = hso.get("permissionDecision") or d.get("decision") or decision
        reason = (hso.get("permissionDecisionReason") or d.get("reason") or reason)
    return decision, reason.strip()


def run_guard(spec: dict) -> dict:
    hook = HOOKS / spec["hook"]
    out = {"guard": spec["guard"], "issue": spec["issue"], "hook": spec["hook"]}

    if not hook.exists():
        out["verdict"] = "UNVERIFIED"
        out["detail"] = f"hook missing: {hook}"
        return out

    with tempfile.TemporaryDirectory(prefix="pob-pos-") as d:
        root = spec["fixture"](Path(d))
        pos = spec["positive"]
        dec, reason = drive(hook, pos["tool_name"], pos["tool_input"](root), root)
        out["positive"] = {"tool": pos["tool_name"], "decision": dec,
                           "reason": reason[:180], "why": pos["why"],
                           "ok": dec in BLOCKED}

    with tempfile.TemporaryDirectory(prefix="pob-neg-") as d:
        root = spec["fixture"](Path(d))
        neg = spec["negative"]
        dec, reason = drive(hook, neg["tool_name"], neg["tool_input"](root), root)
        out["negative"] = {"tool": neg["tool_name"], "decision": dec,
                           "reason": reason[:180], "why": neg["why"],
                           "ok": dec not in BLOCKED}

    if out["positive"]["ok"] and out["negative"]["ok"]:
        out["verdict"] = "PROVEN"
    elif not out["positive"]["ok"]:
        out["verdict"] = "FAILS-OPEN"      # the dangerous one
    else:
        out["verdict"] = "OVER-BLOCKS"     # also a regression
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="write artifacts")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = [run_guard(g) for g in GUARDS]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            v = r["verdict"]
            print(f"\n{r['guard']}  ({r['issue']})   -> {v}")
            for side in ("positive", "negative"):
                if side not in r:
                    print(f"  {r.get('detail','')}")
                    continue
                s = r[side]
                flag = "ok " if s["ok"] else "FAIL"
                want = "must refuse" if side == "positive" else "must permit"
                print(f"  [{flag}] {side:<8} {want:<12} {s['tool']:<34} -> {s['decision']}")
                if not s["ok"]:
                    print(f"         why: {s['why']}")
                    print(f"         got: {s['reason'][:120]}")

    proven = sum(1 for r in results if r["verdict"] == "PROVEN")
    print(f"\n{proven}/{len(results)} guards PROVEN"
          f"   (PROVEN = watched refusing AND still permitting)")
    for r in results:
        if r["verdict"] != "PROVEN":
            print(f"  {r['verdict']}: {r['guard']}")

    if args.record:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        art = {"recorded": datetime.now(timezone.utc).isoformat(),
               "commit": sha, "results": results}
        (ARTIFACTS / "proof-of-block.json").write_text(json.dumps(art, indent=2) + "\n")
        print(f"\nrecorded -> {ARTIFACTS / 'proof-of-block.json'} @ {sha}")

    return 0 if proven == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
