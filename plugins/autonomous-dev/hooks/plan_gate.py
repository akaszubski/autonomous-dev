#!/usr/bin/env python3
"""
Plan Gate - Pre-implementation planning enforcement hook.

Blocks complex Write/Edit operations when no valid plan exists in
.claude/plans/. Follows stick+carrot pattern: blocks with a clear
REQUIRED NEXT ACTION directive pointing to /plan.

Detection strategy:
1. Check if tool is Write or Edit (other tools pass through)
2. Exempt documentation files (.md, CHANGELOG, README, docs/)
3. Check complexity threshold (simple edits < 100 lines pass through)
4. Validate plan exists in .claude/plans/ with required sections
5. Block if no valid plan, with actionable message

Escape hatch: SKIP_PLAN_CHECK=1 environment variable disables all checks.

Exit codes:
    0: Allow (plan valid, doc file, simple edit, or exception/fail-open)

Output: JSON to stdout with hookSpecificOutput for Claude Code hook protocol.

Part of Issue #814: Planning workflow system.
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import os
import sys
from pathlib import Path


# Simple edit threshold -- edits with fewer lines than this are never blocked
SIMPLE_EDIT_LINE_THRESHOLD = 100

# Documentation file patterns that are always allowed
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
DOC_PATHS = {"docs/", "doc/", "documentation/"}
DOC_FILENAMES = {"CHANGELOG", "README", "LICENSE", "CONTRIBUTING", "AUTHORS"}


def _output_decision(
    decision: str,
    reason: str,
    *,
    system_message: str = "",
) -> None:
    """Print hook "decision" as JSON to stdout.

    Uses the Claude Code hook protocol format with permissionDecision field.
    The "decision" value is either "allow" or "block".

    Args:
        decision: "allow" or "block"
        reason: Human-readable reason for the decision
        system_message: Optional message shown to the user
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


def _is_doc_file(file_path: str) -> bool:
    """Check if a file path is a documentation file (always allowed).

    Args:
        file_path: Path to check.

    Returns:
        True if the file is a documentation file.
    """
    path = Path(file_path)

    # Check extension
    if path.suffix.lower() in DOC_EXTENSIONS:
        return True

    # Check if in docs directory
    normalized = file_path.replace("\\", "/")
    for doc_path in DOC_PATHS:
        if normalized.startswith(doc_path) or f"/{doc_path}" in normalized:
            return True

    # Check filename (without extension)
    if path.stem.upper() in DOC_FILENAMES:
        return True

    return False


def _is_simple_edit(tool_name: str, tool_input: dict) -> bool:
    """Check if this is a simple edit below the complexity threshold.

    Simple edits (< 100 lines of new content) are never blocked.

    Args:
        tool_name: The tool being used (Write or Edit).
        tool_input: The tool's input parameters.

    Returns:
        True if the edit is simple enough to skip plan check.
    """
    if tool_name == "Edit":
        new_string = tool_input.get("new_string", "")
        if new_string.count("\n") < SIMPLE_EDIT_LINE_THRESHOLD:
            return True
    elif tool_name == "Write":
        content = tool_input.get("content", "")
        if content.count("\n") < SIMPLE_EDIT_LINE_THRESHOLD:
            return True
    return False


def main() -> int:
    """Main hook entry point.

    Reads PreToolUse hook input from stdin, validates plan existence,
    and outputs JSON decision to stdout.

    Returns:
        0 always (decision communicated via stdout JSON)
    """
    try:
        # Parse stdin
        try:
            input_data = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, Exception):
            # Fail-open: invalid input -> allow
            _output_decision("allow", "Plan gate: invalid input, fail-open")
            return 0

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
        try:
            from hook_bypass import is_bypassed, log_bypass_used
            if is_bypassed():
                log_bypass_used(hook_name=Path(__file__).name, tool_name=tool_name)
                _output_decision("allow", "Universal bypass active (#969)")
                return 0
        except ImportError:
            pass

        # Phase E session-mode gate (Issue #999): when the intent classifier
        # has tagged this session as a low-risk class (conversation, doc,
        # typo, status_query, config) AND the rollout flag is on, skip the
        # plan-gate check entirely. Hard-floor catastrophe checks live in
        # other hooks and are unaffected. On import failure (transitional
        # deploy / cross-cwd / partial uninstall) we fall through to the
        # existing logic.
        try:
            from enforcement_decision import should_skip_enforcement
            from hook_stdin import extract_session_id
            from hook_telemetry import log_block_event

            _phase_e_sid = extract_session_id(input_data)
            _phase_e_skip, _phase_e_reason = should_skip_enforcement(
                hook_name="plan_gate.py",
                function_name=None,
                session_id=_phase_e_sid,
            )
            if _phase_e_skip:
                # Telemetry on the skip path ONLY. The enforce path stays
                # silent — Phase E preserves today's no-event baseline for
                # the common case.
                log_block_event(
                    hook_name="plan_gate.py",
                    decision_shape="mode_skip",
                    reason=_phase_e_reason,
                    session_id=_phase_e_sid,
                )
                _output_decision("allow", f"Phase E skip: {_phase_e_reason}")
                return 0
        except ImportError:
            pass  # transitional deploy — fall through to existing logic

        # Only check Write and Edit tools
        if tool_name not in ("Write", "Edit"):
            _output_decision("allow", f"Plan gate: tool {tool_name} not subject to plan check")
            return 0

        # SKIP_PLAN_CHECK=1 escape hatch
        if os.environ.get("SKIP_PLAN_CHECK") == "1":
            print("Plan gate: SKIP_PLAN_CHECK=1, bypassing all checks", file=sys.stderr)
            _output_decision("allow", "Plan gate: SKIP_PLAN_CHECK=1 bypass")
            return 0

        # Get file path from tool input
        file_path = tool_input.get("file_path", "") or tool_input.get("path", "")

        # Documentation files are always allowed
        if file_path and _is_doc_file(file_path):
            _output_decision("allow", f"Plan gate: doc file exemption for {file_path}")
            return 0

        # Simple edits (< threshold lines) are always allowed
        if _is_simple_edit(tool_name, tool_input):
            _output_decision("allow", "Plan gate: simple edit below threshold")
            return 0

        # Find and validate plan
        # Look for .claude/plans/ relative to git root or cwd
        plans_dir = _find_plans_dir()

        # Import plan_validator (add lib to path)
        hook_dir = Path(__file__).parent
        lib_path = hook_dir.parent / "lib"
        if lib_path.exists():
            sys.path.insert(0, str(lib_path))

        from plan_validator import find_latest_plan, validate_plan

        latest_plan = find_latest_plan(plans_dir)

        if latest_plan is None:
            # No plan file exists -- block
            block_msg = (
                "No planning document found. Complex code changes require a validated plan.\n\n"
                "REQUIRED NEXT ACTION: run /plan to create a planning document before making "
                "complex changes.\n\n"
                "The plan must contain these sections:\n"
                "  - WHY + SCOPE\n"
                "  - Existing Solutions\n"
                "  - Minimal Path\n\n"
                "Escape hatch: set SKIP_PLAN_CHECK=1 to bypass this check."
            )
            _output_decision("block", "Plan gate: no plan file found", system_message=block_msg)
            return 0

        # Validate plan contents
        result = validate_plan(latest_plan)

        if not result.valid:
            missing = ", ".join(result.missing_sections)
            block_msg = (
                f"Plan file exists but is missing required sections: {missing}\n\n"
                "REQUIRED NEXT ACTION: run /plan to update the planning document with "
                "all required sections.\n\n"
                "Required sections:\n"
                "  - WHY + SCOPE\n"
                "  - Existing Solutions\n"
                "  - Minimal Path\n\n"
                "Escape hatch: set SKIP_PLAN_CHECK=1 to bypass this check."
            )
            _output_decision(
                "block",
                f"Plan gate: plan missing sections: {missing}",
                system_message=block_msg,
            )
            return 0

        # Plan is valid -- check expiry (warn only, do not block)
        if result.expired:
            print(
                f"WARNING: Plan is {result.age_hours:.1f} hours old (>72h). "
                f"Consider refreshing with /plan.",
                file=sys.stderr,
            )

        _output_decision("allow", f"Plan gate: valid plan found at {latest_plan}")
        return 0

    except Exception as e:
        # Fail-open: any exception -> allow
        print(f"Plan gate exception (fail-open): {e}", file=sys.stderr)
        _output_decision("allow", f"Plan gate: exception occurred, fail-open: {e}")
        return 0


def _find_plans_dir() -> Path:
    """Find the .claude/plans/ directory.

    Checks cwd first, then walks up to find git root.

    Returns:
        Path to the plans directory (may not exist yet).
    """
    cwd = Path(os.getcwd())

    # Check cwd
    plans_dir = cwd / ".claude" / "plans"
    if plans_dir.exists():
        return plans_dir

    # Walk up to find git root
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current / ".claude" / "plans"
        current = current.parent

    # Fallback to cwd
    return cwd / ".claude" / "plans"



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
