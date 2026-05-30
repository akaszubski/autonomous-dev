#!/usr/bin/env python3
"""
File Organization Enforcer - PreToolUse Write/Edit guard.

Blocks Write/Edit operations that would create files at the repository root
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


def _deny(basename: str, suggested: Optional[str]) -> dict:
    """Construct the JSON deny payload for the Claude Code hook protocol.

    Args:
        basename: The disallowed file basename.
        suggested: Suggested folder (e.g. ``"scripts/"``), or None.

    Returns:
        A dict suitable for ``json.dumps`` and printing to stdout.
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

    # 2. Only act on Write and Edit.
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return 0

    # 3. Extract file_path from tool_input.
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    file_path = tool_input.get("file_path") or ""
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

    # 7. Block.
    suggested = _suggest_folder(basename)
    print(json.dumps(_deny(basename, suggested)))
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
