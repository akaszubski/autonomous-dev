#!/usr/bin/env python3
"""Native-origin run initializer (Issue #1807, A7/A9).

ONE initializer on BOTH native run-initiation events, because the Claude Code
runtime delivers the two origins through different events and the event name is
what distinguishes them:

* ``UserPromptExpansion`` — a USER-TYPED ``/implement`` (any variant). Payload
  carries ``command_name``, ``command_args``, ``command_source``, ``prompt``,
  ``session_id``. This is the only origin class that can carry USER authorization.
* ``PreToolUse`` with ``tool_name=Skill`` — a MODEL-invoked Skill call. A genuinely
  native EVENT, but the model chose to fire it, so it confers no user
  authorization and is never promotable to the typed class.

WHY A NEW HOOK FILE RATHER THAN AN EXISTING ONE. ``UserPromptExpansion`` had no
handler on any surface, so there was nothing to extend there. The PreToolUse half
could have gone into ``unified_pre_tool.py``, and deliberately did not: that file
carries 51 checks behind one shared timeout budget, and a run's ORIGIN record must
not be one of the things silently dropped when that budget overruns. Keeping both
events in one small file also keeps a single owner for the typed-vs-Skill
distinction.

WHAT IT DOES. A typed expansion initializes the run through
``pipeline_completion_state.initialize_native_run_from_event``. A model Skill
call records only a witness through ``record_native_origin_witness``. The
library owns validation and every write. This file adds no policy of its own:
no shell parsing, no environment fallback for the owner, no new store. It is
NON-BLOCKING by construction — it always exits 0, because a recording hook that
can refuse a tool call would be a new gate nobody asked for.

EVIDENCE LIMIT. A payload shape is not provenance: a caller that pipes fabricated
stdin here presents identical fields, ``command_source`` included. The OS boundary
(sandbox denyWrite plus a deny rule for built-in editors) is what would make the
origin unforgeable, and it is NOT part of this slice. A9 is OPEN and UNMEASURED.

Issues: #1807
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code.
import json
import sys
import sys as _sys_953
from pathlib import Path as _Path_953
from typing import Any, Dict, Optional

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.is_dir():
        # The first installed layout owns imports; ambient fallback cannot shadow it.
        while str(_candidate_lib_953) in _sys_953.path:
            _sys_953.path.remove(str(_candidate_lib_953))
        _sys_953.path.insert(0, str(_candidate_lib_953))
        break

try:
    if not (_candidate_lib_953 / "hook_safety.py").is_file():
        raise ImportError("Selected hook library is incomplete")
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    _sys_953.stderr.write("[hook warning] Selected hook library is incomplete; safety wrapper unavailable.\n")
    # Fallback: no-op wrapper so the hook still loads if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


#: Events this initializer acts on. Mirrors the library's own vocabulary; the
#: library refuses anything else, so this is a cheap pre-filter, not a second
#: source of truth.
_ACTED_EVENTS = ("UserPromptExpansion", "PreToolUse")


def _parse_stdin() -> Optional[Dict[str, Any]]:
    """Read the native hook payload from stdin.

    Returns:
        The parsed object, or ``None`` when stdin is absent, empty or not a JSON
        object. A hook must never raise over its own input.
    """
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001 - stdin may be closed
        return None
    if not raw or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def handle_native_origin_event(payload: Any) -> int:
    """Initialize a typed run or record a Skill witness for *payload*.

    The OWNER comes from ``payload['session_id']`` and from nowhere else. There is
    deliberately no ``CLAUDE_SESSION_ID`` fallback here: that variable is
    non-privileged correlation metadata (#1137), and an inherited environment is
    exactly what a descendant process would present.

    Args:
        payload: The parsed native hook stdin.

    Returns:
        Always ``0``. This hook records; it never gates. A payload that is not a
        run initiation is a silent no-op. The library reports refusals on stderr.
    """
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") not in _ACTED_EVENTS:
        return 0

    owner = payload.get("session_id")
    if not isinstance(owner, str) or not owner.strip():
        # No owner in the native payload: nothing to bind a run to. The library
        # reports this too, but returning early keeps a bare PreToolUse storm from
        # emitting a diagnostic per tool call.
        return 0

    try:
        if payload["hook_event_name"] == "UserPromptExpansion":
            from pipeline_completion_state import initialize_native_run_from_event
        else:
            from pipeline_completion_state import record_native_origin_witness
    except ImportError:
        # A stale deployment: say so once, on stderr, and let the run proceed as
        # model-bootstrap origin rather than blocking on a recording hook.
        try:
            sys.stderr.write(
                "[NATIVE-ORIGIN-UNAVAILABLE] native run handling is absent "
                "from the deployed pipeline_completion_state on sys.path; "
                "this run will classify as model-bootstrap origin. REQUIRED NEXT "
                "ACTION: run `bash scripts/deploy-all.sh`\n"
            )
            sys.stderr.flush()
        except Exception:  # pragma: no cover - stderr itself is broken
            pass
        return 0

    try:
        if payload["hook_event_name"] == "UserPromptExpansion":
            initialize_native_run_from_event(payload)
        else:
            record_native_origin_witness(owner.strip(), payload)
    except Exception as exc:  # noqa: BLE001 - recording must never block a tool
        try:
            sys.stderr.write(f"[NATIVE-ORIGIN-UNAVAILABLE] {type(exc).__name__}\n")
        except Exception:  # pragma: no cover - stderr itself is broken
            pass
    return 0


def main() -> int:
    """Hook entry point. Always returns 0."""
    return handle_native_origin_event(_parse_stdin())


# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
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
