#!/usr/bin/env python3
"""
File Organization Enforcer - PreToolUse write guard.

Issue #1503: the tool test is tool_intent.is_write, not a literal
("Write", "Edit") tuple, so MultiEdit / NotebookEdit / MCP editors cannot
route around this hook.

Blocks file-mutating operations that would create files at the repository root
outside of an allow-list (e.g. README.md, pyproject.toml). The hook is
stdlib-only, fails open, and respects the universal AUTONOMOUS_DEV_BYPASS
mechanism (Issue #969).

Allow-list sources:
- Exact filenames from plugins/autonomous-dev/templates/project-structure.json
  ("Root directory" > allowed_files), with fallback to
  .claude/templates/project-structure.json for installed-only repos.
- Hardcoded extension allow-list for config files (.json, .toml, .yaml, etc.).
- Any hidden file (basename starting with ".").

When a file at the root is blocked, the hook returns a suggested folder when
the extension maps to a known directory (e.g. .py -> scripts/, .md -> docs/).
test_*.py / *_test.py files always suggest tests/unit/.

This hook is standalone (NOT wired into unified_pre_tool.py) — it mirrors
plan_gate.py's registration pattern.

Issue: #1034 — Revive enforce_file_organization.py as a live PreToolUse guard.

Exit codes:
    0: Always (decision communicated via stdout JSON).

Output: JSON to stdout with hookSpecificOutput for Claude Code hook protocol.
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return -> exit code, sys.exit -> propagated).
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
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Issue #1503: transport-independent write classification. The lib dir is
# already on sys.path (the _953 block above). The fallback is the literal
# four-tuple — strictly stronger than the ("Write", "Edit") tuple it replaces,
# never weaker.
try:
    from tool_intent import is_write, write_targets
except ImportError:  # pragma: no cover — stale-install fallback
    _FALLBACK_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
    _FALLBACK_PATH_KEYS = ("file_path", "notebook_path", "relative_path", "path")

    def is_write(tool_name: str, tool_input: dict) -> bool:
        """Fallback write test: the literal native write-tool tuple."""
        return tool_name in _FALLBACK_WRITE_TOOLS

    def write_targets(tool_name: str, tool_input: dict) -> list:
        """Fallback target accessor: first non-empty known path key."""
        if not isinstance(tool_input, dict):
            return []
        for _key in _FALLBACK_PATH_KEYS:
            _value = tool_input.get(_key)
            if isinstance(_value, str) and _value:
                return [_value]
        return []


# Issue #1587: refusing and recording are ONE act. ``deny_and_record`` returns
# the deny envelope and appends the hook-blocks.jsonl row in a single call, so
# no caller can obtain a refusal payload without the record happening. On a
# stale install the symbol is None and ``_deny_and_record`` falls through to an
# inline envelope — the write is still refused, just unrecorded.
try:
    from hook_telemetry import deny_and_record as _deny_and_record_lib
except ImportError:  # pragma: no cover — stale-install fallback
    _deny_and_record_lib = None  # type: ignore[assignment]

# Hook identity used for telemetry attribution.
_HOOK_NAME = "enforce_file_organization.py"


# ---------------------------------------------------------------------------
# Configuration constants (hardcoded; project-structure.json supplies only the
# exact-name allow-list — extensions and hidden-file policy live in code).
# ---------------------------------------------------------------------------

# Top-level config file extensions that are always allowed at the repo root.
_ALLOWED_EXTENSIONS = (
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".lock",
)

# When a file is blocked, map the extension to a suggested folder.
# test_*.py / *_test.py files override to tests/unit/ (handled in _suggest_folder).
_SUGGEST_MAP = {
    ".py": "scripts/",
    ".sh": "scripts/",
    ".md": "docs/",
    ".log": "logs/",
    ".jsonl": "logs/",
}

# Built-in allow-list used when project-structure.json is missing/malformed.
# Mirrors the consolidated list from the plan (#1034).
_BUILTIN_ALLOWED_NAMES = frozenset({
    "README.md",
    "README.rst",
    "CHANGELOG.md",
    "CLAUDE.md",
    "PROJECT.md",
    "LICENSE",
    "LICENSE.md",
    "Makefile",
    "Dockerfile",
    "conftest.py",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "poetry.lock",
    "Cargo.toml",
    "go.mod",
    "go.sum",
    "tox.ini",
    ".pre-commit-config.yaml",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Optional[Path]:
    """Resolve the current repo root via ``git rev-parse --show-toplevel``.

    Returns:
        Resolved Path to the repo root, or None when not in a git repo or git
        is unavailable. Subprocess failures are swallowed.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except (OSError, RuntimeError):
        return None


def _load_allowed_names(repo_root: Path) -> set:
    """Load the exact-name allow-list from project-structure.json.

    Reads ``plugins/autonomous-dev/templates/project-structure.json`` first,
    then falls back to ``.claude/templates/project-structure.json`` (for repos
    that only have the installed deployment). Returns the union of the
    built-in allow-list and any names found under ``["structure"]["Root
    directory"]["allowed_files"]``.

    On any I/O error or malformed JSON the function returns the built-in
    allow-list — the hook MUST NOT crash on a missing template.

    Args:
        repo_root: Absolute resolved path to the repo root.

    Returns:
        Set of basenames that are allowed at the repo root.
    """
    names = set(_BUILTIN_ALLOWED_NAMES)

    candidates = (
        repo_root / "plugins" / "autonomous-dev" / "templates" / "project-structure.json",
        repo_root / ".claude" / "templates" / "project-structure.json",
    )
    for candidate in candidates:
        try:
            if not candidate.is_file():
                continue
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        # Look in the documented location first, then a top-level fallback.
        try:
            structure = data.get("structure", {}) if isinstance(data, dict) else {}
            root_block = structure.get("Root directory", {}) if isinstance(structure, dict) else {}
            allowed = root_block.get("allowed_files") if isinstance(root_block, dict) else None
            if allowed is None and isinstance(data, dict):
                allowed = data.get("allowed_files")
            if isinstance(allowed, list):
                for entry in allowed:
                    if isinstance(entry, str) and entry:
                        names.add(entry)
        except (AttributeError, TypeError):
            continue
        # First candidate that parsed wins; later candidates can only add.
    return names


def _is_allowed(basename: str, allowed_names: set) -> bool:
    """Return True iff ``basename`` is permitted at the repo root.

    A file is allowed when ANY of the following is true:
      - basename starts with ``.`` (hidden files like .gitignore, .envrc)
      - basename is in the allow-list (exact match)
      - basename's lowercased extension is in ``_ALLOWED_EXTENSIONS``
    """
    if not basename:
        return False
    if basename.startswith("."):
        return True
    if basename in allowed_names:
        return True
    ext = os.path.splitext(basename)[1].lower()
    if ext in _ALLOWED_EXTENSIONS:
        return True
    return False


def _suggest_folder(basename: str) -> Optional[str]:
    """Return the suggested destination folder for ``basename``, or None.

    Pytest-style filenames (``test_*.py`` and ``*_test.py``) always suggest
    ``tests/unit/``. Otherwise the extension is looked up in ``_SUGGEST_MAP``.
    """
    if not basename:
        return None
    name = basename
    if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
        return "tests/unit/"
    ext = os.path.splitext(name)[1].lower()
    return _SUGGEST_MAP.get(ext)


def _deny_messages(basename: str, suggested: Optional[str]) -> tuple:
    """Build the (reason, system_message) strings for a placement refusal.

    Pure string construction — deliberately NOT a payload builder. The only
    function in this module that yields a deny payload is
    ``_deny_and_record``, which cannot return one without recording it.

    Args:
        basename: The disallowed file basename.
        suggested: Suggested folder (e.g. ``"scripts/"``), or None.

    Returns:
        ``(reason, system_message)``. ``reason`` is model-visible and
        carries the REQUIRED NEXT ACTION directive; ``system_message`` is
        user-visible.
    """
    if suggested:
        suggested_path = f"{suggested}{basename}"
        reason = (
            f"File placement violation: {basename} cannot be created in repo root. "
            f"Suggested location: {suggested_path}. "
            f"REQUIRED NEXT ACTION: Re-issue Write with file_path={suggested_path}."
        )
        sys_msg = (
            f"Blocked Write of {basename} to repo root — suggested location: {suggested}. "
            f"Set AUTONOMOUS_DEV_BYPASS=1 to bypass."
        )
    else:
        reason = (
            f"File placement violation: {basename} cannot be created in repo root. "
            f"No standard folder mapping exists for this file type. "
            f"REQUIRED NEXT ACTION: Move {basename} to an appropriate subdirectory "
            f"(scripts/, docs/, logs/, tests/, etc.) and re-issue the Write."
        )
        sys_msg = (
            f"Blocked Write of {basename} to repo root — no standard folder mapping. "
            f"Set AUTONOMOUS_DEV_BYPASS=1 to bypass."
        )

    return reason, sys_msg


def _deny_and_record(
    basename: str,
    suggested: Optional[str],
    *,
    repo_root: Optional[Path] = None,
    tool_name: str = "",
    file_path: str = "",
    session_id: Optional[str] = None,
) -> dict:
    """Refuse the write AND record the refusal, as a single indivisible act.

    Issue #1587: this hook emitted a valid ``permissionDecision: "deny"``
    and recorded nothing, so every one of its refusals was invisible in
    ``.claude/logs/hook-blocks.jsonl``. The fix is deliberately NOT "add a
    ``log_block_event`` call next to the ``return``" — that reproduces the
    defect class, where refusing and recording are two acts and the second
    is forgettable. This is the ONLY function in this module that produces
    a deny payload, so ``main`` has no path to a refusal that skips the
    record.

    Telemetry never outranks enforcement: if the shared helper is missing
    (stale install) or raises, we fall through to an inline envelope and
    the write is still refused — unrecorded, but refused.

    Args:
        basename: The disallowed file basename.
        suggested: Suggested folder (e.g. ``"scripts/"``), or None.
        repo_root: Repo root, used to anchor the telemetry log so the row
            lands at ``<repo_root>/.claude/logs/hook-blocks.jsonl``
            regardless of the hook's cwd.
        tool_name: Originating tool name, recorded as metadata.
        file_path: Full requested write target, recorded as metadata.
        session_id: Session id from the PreToolUse payload, if present.

    Returns:
        The deny envelope, suitable for ``json.dumps`` and printing.
    """
    reason, sys_msg = _deny_messages(basename, suggested)

    if _deny_and_record_lib is not None:
        try:
            return _deny_and_record_lib(
                hook_name=_HOOK_NAME,
                reason=reason,
                system_message=sys_msg,
                # "dict" == printed JSON envelope, and a member of
                # scripts/hook_perf_report.py BLOCK_SHAPES, so this refusal
                # is counted as a block by the existing report.
                decision_shape="dict",
                hook_event_name="PreToolUse",
                metadata={
                    "tool_name": tool_name,
                    "file_path": file_path,
                    "basename": basename,
                    "suggested_folder": suggested or "",
                    "envelope": "hookSpecificOutput.permissionDecision",
                },
                session_id=session_id,
                start_dir=repo_root,
            )
        except Exception:
            # Recorder failure MUST NOT convert a block into an allow.
            pass

    # Stale install (no hook_telemetry) or recorder failure. The refusal
    # still ships; only the telemetry row is lost.
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
        "systemMessage": sys_msg,
    }


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Read PreToolUse payload from stdin and emit allow/deny JSON to stdout.

    Returns 0 always; the decision is communicated via stdout JSON. The hook
    fails open on any unexpected condition (no git repo, missing tool_input,
    malformed payload) — every fail-open path silently allows by exiting 0
    without printing a JSON envelope (matching the established standalone
    hook contract: absence of a deny envelope = allow).
    """
    # Parse stdin payload
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return 0
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    # 1. Bypass check — env var or .claude/.bypass short-circuits the hook.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(
                hook_name="enforce_file_organization",
                tool_name=str(payload.get("tool_name", "")),
            )
            return 0
    except ImportError:
        # Missing hook_bypass — fail open.
        pass

    # 2. Only act on file-mutating tools. Issue #1503: transport-independent —
    # this hook was bypassable via MultiEdit, NotebookEdit, or any MCP editor.
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    if not is_write(tool_name, tool_input):
        return 0

    # 3. Extract the write target (resolves MCP path keys too).
    _targets = write_targets(tool_name, tool_input)
    file_path = _targets[0] if _targets else (tool_input.get("file_path") or "")
    if not file_path or not isinstance(file_path, str):
        return 0

    # 4. Resolve repo root — non-git contexts skip enforcement.
    repo_root = _repo_root()
    if repo_root is None:
        return 0

    # 5. Resolve the target path and confirm it's directly at the repo root.
    try:
        target = Path(file_path).resolve()
    except (OSError, RuntimeError):
        return 0
    try:
        repo_resolved = repo_root.resolve()
    except (OSError, RuntimeError):
        repo_resolved = repo_root
    if target.parent != repo_resolved:
        return 0

    # 6. Look up the allow-list and decide.
    allowed_names = _load_allowed_names(repo_resolved)
    basename = target.name
    if _is_allowed(basename, allowed_names):
        return 0

    # 7. Block. Refusal and its telemetry row are one call (Issue #1587).
    suggested = _suggest_folder(basename)
    raw_session_id = payload.get("session_id")
    envelope = _deny_and_record(
        basename,
        suggested,
        repo_root=repo_resolved,
        tool_name=str(tool_name),
        file_path=file_path,
        session_id=raw_session_id if isinstance(raw_session_id, str) else None,
    )
    print(json.dumps(envelope))
    return 0


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
