"""Regression tests: the plan-exit gate must deny WRITES, not un-enumerated reads.

FOUND BY THE SPEC-VALIDATOR (#1503 criterion 9), which returned FAIL:

    at stage=plan_exited
      mcp__serena__find_symbol              -> allow
      mcp__searxng__search                  -> DENY   <- mandated search path
      mcp__searxng__fetch                   -> DENY
      mcp__ms365__list-mail-messages        -> DENY
      mcp__home-assistant__ha_get_skill_guide -> DENY

The #1503 fix made the WRITE side classification-based but left the READ side
an enumerated allowlist, merely extending it with Serena. ``MCP_READ_TOOLS``
covers exactly six servers -- serena, playwright and four claude_ai_* -- so a
read-only tool from any other server is denied at this stage. That is the same
"not in the list -> wrong verdict" failure #1503 exists to end, relocated from
writes to reads.

Operational impact: ``mcp__searxng__search`` is the mandated web-search path in
this environment, so a plan-exited session could not do research, while native
``WebFetch`` passed.

POLARITY (maintainer decision, 2026-08-16): deny only what actually acts.

    is_write(tool, input)          -> DENY   (classification, not enumeration)
    tool in MCP_SIDE_EFFECT_TOOLS  -> DENY   (acts without a write shape)
    everything else                -> ALLOW

The explicit side-effect set is required and is NOT a fallback to enumeration:
``mcp__playwright__browser_evaluate`` executes arbitrary JS and carries no
path or content argument, so no shape test can catch it. That specific tool was
called out as AC #19 of the original work and must never be treated as safe.

These tests drive the real hook as a subprocess with a real plan_exited marker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"


def run_hook(tool_name: str, tool_input: dict, cwd: Path) -> str:
    payload = {
        "session_id": "plan-exit-polarity",
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    env = dict(os.environ)
    for k in ("SKIP_PLAN_CHECK", "AUTONOMOUS_DEV_BYPASS",
              "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "ENFORCEMENT_LEVEL"):
        env.pop(k, None)
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=90, cwd=str(cwd), env=env)
    decision = "allow"
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
    return decision


def _make_adev_project(root: Path) -> Path:
    """Make ``root`` look like an autonomous-dev project.

    REQUIRED, and discovered the hard way: the MCP branch of the hook is
    short-circuited by a PROJECT GUARD that emits "Non-autonomous-dev project
    - enforcement skipped" and allows everything. A bare tmp_path therefore
    reproduces nothing -- a first draft of this file allowed BOTH the reads and
    the writers, so its negative controls failed while its defect assertions
    "passed", which is the worst possible combination: a test that cannot
    observe the behaviour it names.

    ``repo_detector.is_autonomous_dev_repo`` requires BOTH the marketplace
    manifest AND a ``.git`` directory -- it documents "Missing .git directory:
    Returns False". A second draft created only the manifest and still
    reproduced nothing, so both are needed.
    """
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "."], cwd=str(root),
                   capture_output=True, check=False)
    marker = root / "plugins" / "autonomous-dev" / ".claude-plugin"
    marker.mkdir(parents=True, exist_ok=True)
    # The detector requires the manifest to CONTAIN the string
    # "autonomous-dev" -- an empty {} passes the exists() check and then
    # fails the content check, which is how three earlier drafts of this
    # fixture silently reproduced nothing.
    (marker / "marketplace.json").write_text('{"name": "autonomous-dev"}')
    return root


@pytest.fixture
def plan_exited(tmp_path):
    """An autonomous-dev project sitting at the plan_exited stage."""
    _make_adev_project(tmp_path)
    (tmp_path / ".claude" / "plan_mode_exit.json").write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": "plan-exit-polarity",
        "stage": "plan_exited",
    }))
    return tmp_path


BLOCKED = {"deny", "block", "ask"}

READ_ONLY_MCP = [
    "mcp__searxng__search",
    "mcp__searxng__fetch",
    "mcp__ms365__list-mail-messages",
    "mcp__home-assistant__ha_get_skill_guide",
    "mcp__obsidian-mcp-tools__search_vault",
    "mcp__serena__find_symbol",
]


class TestReadOnlyMcpToolsAreNotBlocked:
    """THE DEFECT. Reading is not acting; the stage exists to stop acting."""

    @pytest.mark.parametrize("tool", READ_ONLY_MCP)
    def test_read_only_mcp_tool_allowed_at_plan_exited(self, tool, plan_exited):
        assert run_hook(tool, {"query": "x"}, plan_exited) not in BLOCKED, (
            f"{tool} was blocked at plan_exited. Read-only MCP tools must not "
            "be gated by membership of an enumerated allowlist -- that is the "
            "same defect #1503 fixed on the write side."
        )

    def test_searxng_specifically(self, plan_exited):
        """Called out because it is the mandated search path in this env."""
        assert run_hook("mcp__searxng__search", {"query": "python"},
                        plan_exited) not in BLOCKED


class TestActingIsStillBlocked:
    """NEGATIVE CONTROLS. A polarity flip that allows everything is worse
    than the bug -- the stage would stop gating anything at all."""

    @pytest.mark.parametrize("tool,inp", [
        ("mcp__serena__replace_symbol_body",
         {"relative_path": "src/a.py", "name_path": "m", "body": "x\n"}),
        ("mcp__serena__replace_content",
         {"relative_path": "src/a.py", "needle": "a", "repl": "b", "mode": "literal"}),
        ("mcp__serena__delete_lines",
         {"relative_path": "src/a.py", "start_line": 1, "end_line": 400}),
    ])
    def test_mcp_writers_still_denied(self, tool, inp, plan_exited):
        assert run_hook(tool, inp, plan_exited) in BLOCKED, (
            f"{tool} mutates files and must stay blocked at plan_exited."
        )

    def test_browser_evaluate_still_denied(self, plan_exited):
        """AC #19. Executes arbitrary JS, carries no path or content argument,
        so NO shape test can catch it. This is why the explicit side-effect
        set is required and is not a relapse into enumeration."""
        assert run_hook("mcp__playwright__browser_evaluate",
                        {"function": "() => document.title"},
                        plan_exited) in BLOCKED

    def test_native_write_still_denied(self, plan_exited):
        assert run_hook("Write", {"file_path": str(plan_exited / "src" / "a.py"),
                                  "content": "x\n"}, plan_exited) in BLOCKED


class TestGateIsStageScoped:
    """Without the marker the gate must not fire at all, or these tests
    would pass for the wrong reason."""

    def test_writer_allowed_when_no_marker_present(self, tmp_path):
        _make_adev_project(tmp_path)   # adev project, but NO plan_exited marker
        assert run_hook("mcp__serena__replace_content",
                        {"relative_path": "src/a.py", "needle": "a",
                         "repl": "b", "mode": "literal"},
                        tmp_path) not in BLOCKED
