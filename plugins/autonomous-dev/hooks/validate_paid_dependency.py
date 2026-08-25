#!/usr/bin/env python3
"""Refuse writes that introduce a paid-API dependency into production code.

Enforces ONE explicit PROJECT.md OUT-of-Scope entry mechanically (Issue #1639):

    PROJECT.md:59  "Paid features - 100% free, MIT licence"
    INV-8          "No gate requires a paid API, a network call, or a hosted
                    service to function."

Per INV-6 (deterministic before probabilistic) this gate makes NO LLM call --
an LLM alignment judgment would itself need a paid key and so breach the very
rule being enforced.

Detection is by SHAPE, not by an enumerated vendor or filename list: any
callable invocation that is handed an API-credential keyword argument is a
paid-client construction. ``Anthropic(api_key=...)``, ``OpenAI(api_key=...)``
and a never-before-seen ``AcmeLLM(api_token=...)`` are all caught by the same
rule, so the failure does not move to the next file or the next vendor.

Scope: Python production code only. Test files and non-Python files pass
through -- the gate keys on the CONSTRUCTION in production code, not on a
vendor name appearing anywhere.

Escape hatch: ``.claude/.bypass`` (universal), or ``SKIP_PAID_DEPENDENCY_CHECK=1``.
"""

import sys as _sys_953
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",  # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",  # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:  # pragma: no cover - defensive

    def _safe_main_953(_fn):
        _result = _fn()
        _sys_953.exit(_result if isinstance(_result, int) else 0)


import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Credential-shaped keyword names. This is a CATEGORY of argument name, not a
# vendor list -- `foo_api_key`, `apiKey`, `access-token` all match.
_CREDENTIAL_KWARG = (
    r"\w*(?:api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token"
    r"|auth[_-]?token|bearer[_-]?token|subscription[_-]?key)\w*"
)

# A callable invoked with a credential keyword argument -> paid-client construction.
# The bounded `[^()]` gap lets the credential be any position in the arg list while
# stopping the scan at the first nested call, keeping the match local.
_PAID_CLIENT_RE = re.compile(
    r"\b(?P<callee>[A-Za-z_][\w.]*)\s*\(\s*[^()]{0,400}?"
    rf"\b(?P<kwarg>{_CREDENTIAL_KWARG})\s*=(?!=)",
    re.IGNORECASE | re.DOTALL,
)

# `def f(api_key=None)` / `async def f(*, api_token="")` are DECLARATIONS of a
# parameter default, not constructions of a client. Stripped before scanning so
# the gate cannot cry wolf on ordinary function signatures.
_DEF_SIGNATURE_RE = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+\w+[ \t]*\(", re.MULTILINE)

_TEST_DIR_PARTS = {"tests", "test", "testing"}


def _emit(decision: str, reason: str) -> None:
    """Print a Claude Code PreToolUse decision envelope to stdout."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def is_production_python(file_path: str) -> bool:
    """Return True when ``file_path`` is Python production code.

    Args:
        file_path: Target path of the write.

    Returns:
        True for ``.py`` files outside any test directory or test module.
    """
    if not file_path:
        return False
    path = Path(file_path)
    if path.suffix != ".py":
        return False
    if _TEST_DIR_PARTS & {p.lower() for p in path.parts}:
        return False
    name = path.name
    return not (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def find_paid_client(content: str) -> Optional[str]:
    """Return the offending construction snippet, or None when content is clean.

    Args:
        content: The code the write would introduce.

    Returns:
        A short ``Callee(... kwarg=`` snippet naming the violation, else None.
    """
    if not content:
        return None
    # Blank out `def ...(` openers so parameter defaults are not read as calls.
    scannable = _DEF_SIGNATURE_RE.sub(lambda m: " " * len(m.group(0)), content)
    match = _PAID_CLIENT_RE.search(scannable)
    if match is None:
        return None
    return f"{match.group('callee')}(... {match.group('kwarg')}=...)"


def main() -> int:
    """Read a PreToolUse payload from stdin and allow or deny the write."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return 0  # Malformed input is not this gate's business.

    if os.environ.get("SKIP_PAID_DEPENDENCY_CHECK") == "1":
        return 0
    try:
        from hook_bypass import is_bypassed

        if is_bypassed():
            return 0
    except ImportError:
        pass

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    # Fail CLOSED on classifier loss. Without this the hook fails open (loudly,
    # via hook_safety) whenever tool_intent cannot be imported -- a guard that
    # evaporates exactly when the enforcement stack is damaged. The other eight
    # guards in proof_of_block.py refuse under this same injected fault.
    try:
        from tool_intent import changed_content, is_write, write_targets
    except ImportError as exc:
        _emit(
            "deny",
            f"BLOCKED: paid-dependency gate cannot classify this write ({exc}).\n"
            "Refusing rather than failing open -- the PROJECT.md:59 paid-features "
            "check is unavailable, so this write is unverified.\n\n"
            "REQUIRED NEXT ACTION: repair plugins/autonomous-dev/lib/tool_intent.py "
            "(or reinstall via `bash scripts/deploy-all.sh`), then retry.\n"
            "Emergency override: SKIP_PAID_DEPENDENCY_CHECK=1",
        )
        return 0

    if not is_write(tool_name, tool_input):
        return 0

    targets = write_targets(tool_name, tool_input) or []
    if not any(is_production_python(t) for t in targets):
        return 0

    offender = find_paid_client(changed_content(tool_name, tool_input))
    if offender is None:
        return 0

    target = next(t for t in targets if is_production_python(t))
    _emit(
        "deny",
        f"BLOCKED: paid-API client construction in production code -- {offender} in {target}\n\n"
        "PROJECT.md:59 lists 'Paid features' as OUT of Scope (100% free, MIT licence), "
        "and INV-8 requires that no gate depend on a paid API, a network call, or a "
        "hosted service to function.\n\n"
        "REQUIRED NEXT ACTION -- pick one:\n"
        "  1. Use a free local path instead (subprocess `claude -p`, or a deterministic check).\n"
        "  2. Move the credential-bearing code into a test/ fixture if it is test-only.\n"
        "  3. If this genuinely belongs in scope, amend .claude/PROJECT.md OUT of Scope "
        "FIRST with the tradeoff argued, then retry.\n"
        "Emergency override: SKIP_PAID_DEPENDENCY_CHECK=1",
    )
    return 0


try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - defensive

    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass


def _timed_main() -> int:
    with HookTimer(_Path_953(__file__).name):
        return main()


if __name__ == "__main__":
    _safe_main_953(_timed_main)
