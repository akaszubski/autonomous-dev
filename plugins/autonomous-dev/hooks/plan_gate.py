#!/usr/bin/env python3
"""
Plan Gate - Pre-implementation planning enforcement hook.

Blocks complex file-mutating operations when no valid plan exists in
.claude/plans/. Follows stick+carrot pattern: blocks with a clear
REQUIRED NEXT ACTION directive pointing to /plan.

Detection strategy:
1. Classify the tool via tool_intent.is_write (Issue #1503) — every write
   transport is covered (Write, Edit, MultiEdit, NotebookEdit, MCP editors),
   not just the two native ones. Non-writers pass through.
2. Exempt documentation files (.md, CHANGELOG, README, docs/)
3. Check complexity threshold against the CHANGE, not the transport
   (simple edits < 100 lines pass through)
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

# Issue #1611: fuse recording to refusal. Before this, plan_gate's TWO enforce
# paths called ``_output_decision("block", ...)`` and recorded nothing, while
# its Phase-E SKIP path was the only thing writing to hook-blocks.jsonl. Every
# one of its 287 rows in the live log was a ``mode_skip``; however many writes
# it has actually blocked, the log holds no trace of any of them.
#
# ``block_event_decorator`` is one of the three sanctioned sinks (see
# tests/unit/hooks/test_refusal_sink_ratchet.py) and is the one that PRESERVES
# THE EMITTED ENVELOPE: it wraps this hook's sole refusal emitter without
# touching what that emitter prints. The other two sinks would have rewritten
# the payload — ``HookDecision`` normalises a PreToolUse refusal to
# ``permissionDecision: "deny"`` and emits nothing at all on an allow, so
# migrating to it would have changed live enforcement behaviour on all 11
# call sites — the 9 allows included, since they emit an envelope this hook's
# callers depend on. A refusal that changed shape because it started recording is
# exactly the trade this migration must not make.
#
# ``refusal_values={"block"}`` records the out-of-enum value this hook
# actually emits. That divergence (PreToolUse's enum is ``allow|deny|ask``) is
# real and is Issue #1589's to resolve; it is named here rather than silently
# preserved, and it is NOT fixed here — changing "block" to "deny" would alter
# what Claude Code receives, which is a separate change with a separate blast
# radius.
try:
    from hook_telemetry import block_event_decorator
except ImportError:  # pragma: no cover — stale-install fallback
    def block_event_decorator(_hook_name, **_kwargs):
        """No-op fallback: refuse unrecorded rather than not refuse at all."""

        def _decorator(fn):
            return fn

        return _decorator


# Issue #1503: transport-independent write classification. The lib dir is
# already on sys.path (the _953 block above). The fallback keeps this hook
# working against a stale install and is STRICTLY STRONGER than the legacy
# ("Write", "Edit") tuple it replaces — never weaker.
try:
    from tool_intent import CONTENT_KEYS, changed_content, is_write, write_targets
except ImportError:  # pragma: no cover — stale-install fallback
    _FALLBACK_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
    _FALLBACK_PATH_KEYS = ("file_path", "notebook_path", "relative_path", "path")
    _FALLBACK_CONTENT_KEYS = ("content", "new_string", "body", "repl", "new_source")
    CONTENT_KEYS = _FALLBACK_CONTENT_KEYS

    def is_write(tool_name: str, tool_input: dict) -> bool:
        """Fallback write test: the literal native write-tool tuple."""
        return tool_name in _FALLBACK_WRITE_TOOLS

    def changed_content(tool_name: str, tool_input: dict) -> str:
        """Fallback content accessor: first non-empty known content key."""
        if not isinstance(tool_input, dict):
            return ""
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            parts = [
                e.get("new_string")
                for e in edits
                if isinstance(e, dict) and isinstance(e.get("new_string"), str)
            ]
            if parts:
                return "\n".join(p for p in parts if p)
        for _key in _FALLBACK_CONTENT_KEYS:
            _value = tool_input.get(_key)
            if isinstance(_value, str) and _value:
                return _value
        return ""

    def write_targets(tool_name: str, tool_input: dict) -> list:
        """Fallback target accessor: first non-empty known path key."""
        if not isinstance(tool_input, dict):
            return []
        for _key in _FALLBACK_PATH_KEYS:
            _value = tool_input.get(_key)
            if isinstance(_value, str) and _value:
                return [_value]
        return []


# Simple edit threshold -- edits with fewer lines than this are never blocked
SIMPLE_EDIT_LINE_THRESHOLD = 100

# Issue #1503 follow-up: write transports whose changed_content() does not
# BOUND the size of the change. replace_in_files rewrites an unbounded set of
# files from one small ``repl``, so content length says nothing about blast
# radius. This is NOT a second write-classification scheme — tool_intent
# .is_write() remains the only answer to "is this a write?"; this set answers
# the separate question "does the content bound the size?".
UNBOUNDED_CHANGE_TOOLS = frozenset({"mcp__serena__replace_in_files"})

# Security finding F5 (#1503 re-audit): transports that carry NO content
# argument in their real schema. These MUST be rejected by NAME, before any
# key inspection, because the PreToolUse hook receives tool_input straight
# from the model's tool-call arguments — before the MCP server validates them
# against its own schema. Without this, appending a throwaway ``content: ""``
# to a safe_delete_symbol call forged the simple-edit exemption (measured).
# Trusting key PRESENCE is only sound for tools whose schema actually
# declares that key; for these it never does.
NO_CONTENT_ARG_TOOLS = frozenset(
    {
        "mcp__serena__rename_symbol",
        "mcp__serena__safe_delete_symbol",
        "mcp__serena__delete_lines",
        "mcp__serena__delete_memory",
        "mcp__serena__rename_memory",
    }
)

# Memory-store mutations DO declare a content argument, so they are not
# content-less -- but content length still fails to bound their blast radius,
# and a memory write is not a source edit, so the source-edit simple-edit
# exemption should not apply to them either. Separate predicate, separate
# name, so NO_CONTENT_ARG_TOOLS keeps stating something true.
NON_SOURCE_MUTATION_TOOLS = frozenset(
    {
        "mcp__serena__write_memory",
        "mcp__serena__edit_memory",
    }
)

# Documentation file patterns that are always allowed
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
DOC_PATHS = {"docs/", "doc/", "documentation/"}
DOC_FILENAMES = {"CHANGELOG", "README", "LICENSE", "CONTRIBUTING", "AUTHORS"}


#: Structured metadata stamped on every refusal row this hook records.
#:
#: A recorded row carries ``hook_name``, ``decision_shape="dict"``, ``reason``
#: and ``refused=true`` — and none of those says WHICH decision value went out
#: on the wire. A plan_gate row is therefore byte-comparable to a genuine,
#: honoured ``deny`` from ``unified_pre_tool.py``. Before #1611 this hook's
#: refusals were an unknowable zero, which reads honestly as NO EVIDENCE;
#: recording them without this metadata would convert that into a confident
#: positive count that may be counting refusals the client never honoured — a
#: third direction of error, in an issue about an instrument wrong in two.
#:
#: ``honoured: "unverified"`` is the load-bearing field. It is not a hedge: the
#: value ``"block"`` is outside ``PreToolUse``'s ``allow|deny|ask`` enum, and
#: nothing in this repo has observed what Claude Code does with it. #1589 owns
#: answering that. Until it does, these rows are separable from the verified
#: ones by a single query, and the claim stays as strong as the evidence.
REFUSAL_METADATA = {
    "permission_decision": "block",
    "protocol_enum_divergence": "PreToolUse enum is allow|deny|ask",
    "honoured": "unverified",
    "issue": 1589,
}


@block_event_decorator(
    "plan_gate.py",
    decision_shape="dict",
    refusal_values=frozenset({"block"}),
    metadata=REFUSAL_METADATA,
)
def _output_decision(
    decision: str,
    reason: str,
    *,
    system_message: str = "",
) -> None:
    """Print hook "decision" as JSON to stdout.

    Uses the Claude Code hook protocol format with permissionDecision field.
    The "decision" value is either "allow" or "block".

    This is plan_gate's SOLE refusal emitter — all 11 decision sites route
    through it (9 allow, 2 block). Decorating it with
    ``block_event_decorator`` (Issue #1611)
    therefore fuses recording to refusal by construction: there is no path on
    which this hook can block a write and leave no row. The decorator does not
    alter the printed payload, so the envelope Claude Code receives is
    byte-identical to the pre-#1611 one on every path, refusing and permitting
    alike.

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


def _has_size_proxy(tool_name: str, tool_input: dict) -> bool:
    """Return True when ``changed_content`` faithfully bounds the change size.

    Presence, NOT truthiness: a native ``Write`` with ``content: ""`` or an
    ``Edit`` with ``new_string: ""`` does carry a content signal — the change
    is genuinely empty, hence genuinely simple, and stays exempt. The serena
    writers that carry no content argument at all (``rename_symbol``,
    ``safe_delete_symbol``, ``delete_lines``, and the memory mutators) do not:
    ``changed_content`` returns "" and the line count is 0 no matter how many
    lines the call removes, so they must fall through to the plan requirement.

    Issue #1503 follow-up (reviewer FINDING-1 / security-auditor F3).

    Args:
        tool_name: The tool being used.
        tool_input: The tool's input parameters.

    Returns:
        True if content length is a faithful proxy for the change size.
    """
    if (
        tool_name in UNBOUNDED_CHANGE_TOOLS
        or tool_name in NO_CONTENT_ARG_TOOLS
        or tool_name in NON_SOURCE_MUTATION_TOOLS
    ):
        return False
    if not isinstance(tool_input, dict):
        return False
    if isinstance(tool_input.get("edits"), list):
        return True
    return any(isinstance(tool_input.get(key), str) for key in CONTENT_KEYS)


def _is_simple_edit(tool_name: str, tool_input: dict) -> bool:
    """Check if this is a simple edit below the complexity threshold.

    Simple edits (< 100 lines of new content) are never blocked.

    Issue #1503: the exemption is about the CHANGE, not the TRANSPORT. The
    per-tool_name branches this replaced returned False for MultiEdit,
    NotebookEdit, and every MCP editor, so a 5-line MultiEdit was gated while
    an identical 5-line Edit sailed through. ``changed_content`` resolves the
    written content for every transport, so one line-count rule now covers
    all of them.

    Issue #1503 follow-up: a transport with no content argument has no size
    proxy — ``changed_content`` returns "" and the line count is 0 however
    destructive the call. Those transports are NOT simple and fall through to
    the plan requirement. See ``_has_size_proxy``.

    Args:
        tool_name: The tool being used.
        tool_input: The tool's input parameters.

    Returns:
        True if the edit is simple enough to skip plan check.
    """
    if not _has_size_proxy(tool_name, tool_input):
        return False
    content = changed_content(tool_name, tool_input)
    return content.count("\n") < SIMPLE_EDIT_LINE_THRESHOLD


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

        # Only check file-mutating tools. Issue #1503: transport-independent —
        # MultiEdit, NotebookEdit and MCP editors are writes too.
        if not is_write(tool_name, tool_input):
            _output_decision("allow", f"Plan gate: tool {tool_name} not subject to plan check")
            return 0

        # SKIP_PLAN_CHECK=1 escape hatch
        if os.environ.get("SKIP_PLAN_CHECK") == "1":
            print("Plan gate: SKIP_PLAN_CHECK=1, bypassing all checks", file=sys.stderr)
            _output_decision("allow", "Plan gate: SKIP_PLAN_CHECK=1 bypass")
            return 0

        # Get file path from tool input. Issue #1503: write_targets resolves
        # MCP path keys (relative_path) as well as the native ones; the
        # explicit "path" fallback is retained for tools it does not know.
        _targets = write_targets(tool_name, tool_input)
        file_path = _targets[0] if _targets else (
            tool_input.get("file_path", "") or tool_input.get("path", "")
        )

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
