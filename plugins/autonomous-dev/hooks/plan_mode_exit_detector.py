#!/usr/bin/env python3
"""
Plan Mode Exit Detector - Writes marker when ExitPlanMode tool is used.

Hook: PostToolUse (runs after every tool call)

When the model exits plan mode (ExitPlanMode tool), this hook writes a
marker file at `.claude/plan_mode_exit.json` containing:
- timestamp: ISO 8601 UTC timestamp
- session_id: Current session ID from environment
- stage: "plan_exited" (initial stage of the 2-stage enforcement pipeline)

The marker is read by unified_prompt_validator.py as part of the staged
plan-exit pipeline: plan_exited → (plan-critic runs) → critique_done →
/implement allowed. A systemMessage is output to instruct the model to
invoke plan-critic before proceeding.

Scope/escape gating (Issue #938):
- When deployed user-globally (~/.claude/hooks), the hook is silent in foreign
  projects (no marker, no message) unless AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1.
- Three escape hatches bypass enforcement (in any project):
    AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=<truthy>   (env var, cross-session)
    .claude/SKIP_PLAN_REVIEW                   (sentinel file)
    /implement --skip-review                   (one-shot, plan-only)

Exit codes:
    0: Always (PostToolUse cannot block)
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
from datetime import datetime, timezone
from pathlib import Path


MARKER_PATH = ".claude/plan_mode_exit.json"


# Defensive import of repo_detector (Issue #938).
# Mirrors unified_pre_tool.py:107-143. Uses importlib.util.spec_from_file_location
# so the import resolves correctly when this hook runs from ~/.claude/hooks/
# (user-global) or plugins/autonomous-dev/hooks/ (in-project).
# Fail-closed: if detector is unavailable, _is_adev_project() returns True.
_is_adev_project_fn = None
try:
    _hook_dir = Path(__file__).resolve().parent
    _repo_detector_candidates = [
        _hook_dir.parent / "lib" / "repo_detector.py",            # plugins/autonomous-dev/lib
        _hook_dir.parents[2] / "lib" / "repo_detector.py",         # fallback
        Path.home() / ".claude" / "lib" / "repo_detector.py",      # user-global install
    ]
    for _rd_path in _repo_detector_candidates:
        if _rd_path.exists():
            import importlib.util as _rd_ilu
            _rd_spec = _rd_ilu.spec_from_file_location("repo_detector", str(_rd_path))
            if _rd_spec and _rd_spec.loader:
                _rd_mod = _rd_ilu.module_from_spec(_rd_spec)
                _rd_spec.loader.exec_module(_rd_mod)
                _is_adev_project_fn = _rd_mod.is_autonomous_dev_repo
            break
except Exception:
    _is_adev_project_fn = None  # Fail closed (always enforce)


def _is_adev_project() -> bool:
    """Return True if cwd is an autonomous-dev repo. Fail-closed."""
    if _is_adev_project_fn is None:
        return True
    return _is_adev_project_fn()


def _truthy(val: str) -> bool:
    """Recognize common truthy strings ("1", "true", "yes", "on" — case-insensitive)."""
    return val.strip().lower() in ("1", "true", "yes", "on")


def main() -> int:
    """
    Main hook entry point.

    Reads stdin for PostToolUse hook input. If the tool_name is
    "ExitPlanMode", writes the plan mode exit marker file.

    Returns:
        0: Always (non-blocking hook)
    """
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        return 0

    tool_name = input_data.get("tool_name", "")

    # Universal bypass (Issue #969): falls through to allow with telemetry.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name=tool_name)
            return 0
    except ImportError:
        pass

    if tool_name != "ExitPlanMode":
        return 0

    # Issue #938: Scope/escape gates (precedence: escape > scope > default).
    cwd = Path(os.getcwd())
    env_skip = _truthy(os.environ.get("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", ""))
    sentinel = (cwd / ".claude" / "SKIP_PLAN_REVIEW").exists()
    global_enforce = _truthy(os.environ.get("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", ""))
    is_adev = _is_adev_project()
    in_scope = global_enforce or is_adev

    # Gate 1: Escape hatch wins. Warning is only emitted for genuine
    # autonomous-dev projects so foreign-project bypasses stay silent
    # (even when GLOBAL_ENFORCEMENT is opted in).
    if env_skip or sentinel:
        if is_adev:
            warning = (
                "PLAN-CRITIC BYPASS — Plan critique skipped via "
                + ("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW env var" if env_skip
                   else ".claude/SKIP_PLAN_REVIEW sentinel")
                + ". Proceeding without critique. Unset to re-enable."
            )
            try:
                print(json.dumps({
                    "hookSpecificOutput": {"hookEventName": "PostToolUse"},
                    "systemMessage": warning,
                }))
            except Exception:
                pass
        return 0

    # Gate 2: Out of scope — silent no-op.
    if not in_scope:
        return 0

    # Gate 3: In scope, no escape — fall through to existing marker-write logic.

    # Write marker file
    try:
        marker_path = Path(os.getcwd()) / MARKER_PATH
        marker_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract plan content from tool_response if available
        tool_response = input_data.get("tool_response", {})
        plan_content = ""
        if isinstance(tool_response, dict):
            plan_content = tool_response.get("plan", "") or tool_response.get("content", "") or ""
        elif isinstance(tool_response, str):
            plan_content = tool_response

        # AC#3 (Issue #937, #970): If plan-critic produced a PROCEED verdict
        # BEFORE ExitPlanMode fires (e.g. critic invoked during plan mode),
        # the verdict file is sitting at .claude/plan_critic_verdict.json
        # waiting to be consumed. Without this branch the marker is born at
        # stage="plan_exited" and the verdict file is left dangling — the
        # subsequent stage-advance helper short-circuits because the marker
        # is already past plan_exited by the time it observes critique.
        # Result: the user is wedged behind the plan-critic gate even though
        # plan-critic already PROCEEDed.
        verdict_path = cwd / ".claude" / "plan_critic_verdict.json"
        proceeded, _verdict_ts = _plan_critic_proceeded(verdict_path)
        stage_value = "critique_done" if proceeded else "plan_exited"

        marker_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
            "stage": stage_value,
        }

        if proceeded:
            marker_data["critique_completed_at"] = datetime.now(timezone.utc).isoformat()
            # Consume verdict file so it cannot replay against a future plan.
            try:
                verdict_path.unlink(missing_ok=True)
            except OSError:
                pass

        # Add plan content if available (truncate to 10K chars)
        if plan_content:
            marker_data["plan_content"] = plan_content[:10000]

        marker_path.write_text(json.dumps(marker_data, indent=2))

        # Output systemMessage — branches on whether plan-critic already PROCEEDed.
        if proceeded:
            system_msg = (
                "PLAN MODE EXITED — plan-critic already PROCEEDed; pipeline ready. "
                "You may now run /implement or /plan-to-issues."
            )
        else:
            system_msg = (
                "PLAN MODE EXITED — Plan critique required before proceeding.\n\n"
                "You MUST invoke the plan-critic agent on the plan you just created. "
                "After plan-critic completes with PROCEED verdict, the stage will "
                "automatically advance and you can proceed with /implement or /plan-to-issues.\n\n"
                "Escape hatches (any one):\n"
                "  - /implement --skip-review                       (one-shot)\n"
                "  - export AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1       (cross-session, recommended)\n"
                "  - touch .claude/SKIP_PLAN_REVIEW                 (local, gitignored)"
            )
        output = {
            "hookSpecificOutput": {"hookEventName": "PostToolUse"},
            "systemMessage": system_msg,
        }
        print(json.dumps(output))
    except Exception:
        # Never block on marker write or system message output failure
        pass

    return 0


def _plan_critic_proceeded(verdict_path: Path):
    """Return (True, verdict_ts) iff plan-critic verdict file declares PROCEED.

    AC#3 helper (Issue #937, #970). Reads the verdict JSON file written by
    plan-critic and validates:

    - File exists and parses as JSON.
    - ``verdict`` field equals ``"PROCEED"`` (REVISE/BLOCKED → False).
    - ``timestamp`` field is parseable ISO 8601.

    Staleness checks (e.g. verdict newer than marker) are NOT applied here —
    when this helper runs from ``main()`` no marker exists yet, so freshness
    is an inherently future check delegated to ``_advance_plan_mode_stage``
    in ``unified_session_tracker.py``.

    Args:
        verdict_path: Absolute path to ``.claude/plan_critic_verdict.json``.

    Returns:
        Tuple ``(proceeded: bool, verdict_ts: datetime | None)``.
    """
    try:
        if not verdict_path.exists():
            return (False, None)
        data = json.loads(verdict_path.read_text())
        if not isinstance(data, dict):
            return (False, None)
        if data.get("verdict") != "PROCEED":
            return (False, None)
        ts_raw = data.get("timestamp")
        if not isinstance(ts_raw, str) or not ts_raw:
            return (False, None)
        try:
            verdict_ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            return (False, None)
        return (True, verdict_ts)
    except (json.JSONDecodeError, OSError, ValueError):
        return (False, None)


if __name__ == "__main__":
    _safe_main_953(main)
