#!/usr/bin/env python3
"""
Context-File Size Guard Hook

Warns when project context files exceed their target sizes. This is a
NON-BLOCKING warning-only hook — always exits 0 regardless of findings.

What it checks:
- CLAUDE.md in the repo root: warns if > 200 lines (Anthropic best practice).
- .claude/PROJECT.md in the repo root: warns if > 150 lines
  (content-allocation target, see docs/development/CONTENT_ALLOCATION.md).
- ~/.claude/projects/<slug>/memory/MEMORY.md: warns if > 200 lines
  (Anthropic auto-load threshold). The slug is derived from the current
  working directory by replacing '/' with '-'.

Each file is checked independently. Missing files are silently skipped
(no warning, no error). A failure in one check does not block the others.

Usage:
    Add to settings.local.json or settings.autonomous-dev.json PreCommit hooks:
    {
      "hooks": {
        "PreCommit": [
          {
            "type": "command",
            "command": "python \"$(git rev-parse --show-toplevel)/plugins/autonomous-dev/hooks/validate_claude_md_size.py\""
          }
        ]
      }
    }

Exit codes:
- 0: Always (non-blocking warning hook)
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


import sys
from pathlib import Path
from typing import Tuple

MAX_LINES = 200
MAX_PROJECT_LINES = 150  # PROJECT.md (docs/development/CONTENT_ALLOCATION.md)
MAX_MEMORY_LINES = 200   # MEMORY.md (Anthropic auto-load threshold)


def get_repo_root() -> Path:
    """Find repository root by traversing up to .git directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


def derive_memory_path() -> Path:
    """Derive the auto-load MEMORY.md path for the current working directory.

    Claude stores per-project auto-memory at
    ``~/.claude/projects/<slug>/memory/MEMORY.md`` where ``<slug>`` is the
    absolute path of the current working directory with '/' replaced by '-'.

    Returns:
        Path to MEMORY.md for the current cwd. The file may not exist —
        callers must handle that case.
    """
    slug = str(Path.cwd()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"


def check_project_md_size(repo_root: Path) -> Tuple[int, str]:
    """Check .claude/PROJECT.md size against the content-allocation target.

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Tuple of (line_count, warning_message).
        line_count is 0 if PROJECT.md is missing or unreadable.
        warning_message is empty string if no warning needed.
    """
    project_md_path = repo_root / ".claude" / "PROJECT.md"

    if not project_md_path.exists():
        return 0, ""

    try:
        content = project_md_path.read_text(encoding="utf-8")
    except OSError:
        return 0, ""

    line_count = len(content.splitlines())

    if line_count <= MAX_PROJECT_LINES:
        return line_count, ""

    warning = (
        f"WARNING: .claude/PROJECT.md is {line_count} lines "
        f"(content-allocation target: keep under {MAX_PROJECT_LINES}). "
        f"Current: {line_count}/{MAX_PROJECT_LINES}"
    )
    return line_count, warning


def check_memory_md_size() -> Tuple[int, str]:
    """Check the per-project auto-memory MEMORY.md against Anthropic's auto-load threshold.

    Returns:
        Tuple of (line_count, warning_message).
        line_count is 0 if MEMORY.md is missing or unreadable.
        warning_message is empty string if no warning needed.
    """
    memory_md_path = derive_memory_path()

    if not memory_md_path.exists():
        return 0, ""

    try:
        content = memory_md_path.read_text(encoding="utf-8")
    except OSError:
        return 0, ""

    line_count = len(content.splitlines())

    if line_count <= MAX_MEMORY_LINES:
        return line_count, ""

    warning = (
        f"WARNING: MEMORY.md is {line_count} lines "
        f"(Anthropic auto-load threshold: {MAX_MEMORY_LINES}). "
        f"Current: {line_count}/{MAX_MEMORY_LINES} — file: {memory_md_path}"
    )
    return line_count, warning


def check_claude_md_size(repo_root: Path) -> Tuple[int, str]:
    """Check CLAUDE.md size and return (line_count, warning_message).

    Args:
        repo_root: Path to the repository root directory.

    Returns:
        Tuple of (line_count, warning_message).
        line_count is 0 if CLAUDE.md not found.
        warning_message is empty string if no warning needed.
    """
    claude_md_path = repo_root / "CLAUDE.md"

    if not claude_md_path.exists():
        return 0, ""

    content = claude_md_path.read_text(encoding="utf-8")
    line_count = len(content.splitlines())

    if line_count <= MAX_LINES:
        return line_count, ""

    warning = (
        f"WARNING: CLAUDE.md is {line_count} lines "
        f"(Anthropic best practice: keep under {MAX_LINES}). "
        f"Current: {line_count}/{MAX_LINES}"
    )
    return line_count, warning


def main() -> int:
    """Run all context-file size checks (CLAUDE.md, PROJECT.md, MEMORY.md).

    Each check runs in isolation — a failure in one check (e.g. OSError)
    does not suppress the others. All warnings are printed to stderr.

    Returns:
        Always 0 (non-blocking warning hook).
    """
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="validate_claude_md_size")
            return 0
    except ImportError:
        pass

    repo_root = get_repo_root()

    # CLAUDE.md check (repo root).
    try:
        _, warning = check_claude_md_size(repo_root)
        if warning:
            print(warning, file=sys.stderr)
    except OSError:
        # One check's failure must not block the others.
        pass

    # .claude/PROJECT.md check (content-allocation target).
    try:
        _, warning = check_project_md_size(repo_root)
        if warning:
            print(warning, file=sys.stderr)
    except OSError:
        pass

    # MEMORY.md check (per-project auto-memory under ~/.claude/projects/).
    try:
        _, warning = check_memory_md_size()
        if warning:
            print(warning, file=sys.stderr)
    except OSError:
        pass

    return 0



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
