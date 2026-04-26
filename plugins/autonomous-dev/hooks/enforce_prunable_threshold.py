#!/usr/bin/env python3
"""
PreCommit hook: Block commits when prunable test count exceeds threshold.

Prevents test pruning rebound by enforcing a ceiling on the number of
prunable test candidates in the codebase. Uses local-only AST scanning
via TestPruningAnalyzer -- no network calls.

Issue #863: PreCommit hook that blocks commits when prunable test count
exceeds threshold, preventing test pruning rebound.
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


import os
import subprocess
import sys
from pathlib import Path


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ


# Fallback for non-UV environments -- add lib to sys.path
if not is_running_under_uv():
    hook_dir = Path(__file__).resolve().parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
    # Also try the installed location
    installed_lib = hook_dir.parent.parent / "lib"
    if installed_lib.exists():
        sys.path.insert(0, str(installed_lib))

# Import local-only analyzer and threshold constant
try:
    from test_lifecycle_manager import PRUNABLE_THRESHOLD
    from test_pruning_analyzer import TestPruningAnalyzer
except ImportError:
    # If the libraries are not available, allow the commit (graceful degradation)
    sys.exit(0)


def get_project_root() -> "Path | None":
    """Find the project root via git rev-parse.

    Returns:
        Path to the project root, or None if not in a git repo or command fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return None


def count_prunable(project_root: Path) -> int:
    """Count prunable findings using TestPruningAnalyzer (local AST scan only).

    Args:
        project_root: Path to the project root directory.

    Returns:
        Number of findings where prunable is True.
    """
    analyzer = TestPruningAnalyzer(project_root)
    report = analyzer.analyze()
    return sum(1 for finding in report.findings if finding.prunable)


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        0 to allow the commit, 2 to block it.
    """
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="PreCommit")
            return 0
    except ImportError:
        pass

    # Check skip environment variable
    if os.environ.get("SKIP_PRUNABLE_GATE") == "1":
        return 0

    # Find project root
    project_root = get_project_root()
    if project_root is None:
        return 0

    # Count prunable findings -- graceful degradation on known error types
    try:
        prunable_count = count_prunable(project_root)
    except (OSError, RuntimeError, AttributeError) as e:
        print(
            f"enforce_prunable_threshold: analyzer error, skipping gate: {e}",
            file=sys.stderr,
        )
        return 0

    # Block if above threshold
    if prunable_count > PRUNABLE_THRESHOLD:
        print(
            f"BLOCKED: Prunable test count ({prunable_count}) exceeds threshold ({PRUNABLE_THRESHOLD}).\n"
            f"\n"
            f"The codebase has {prunable_count} prunable test candidates, which is above the\n"
            f"maximum allowed threshold of {PRUNABLE_THRESHOLD}.\n"
            f"\n"
            f"REQUIRED NEXT ACTION: Run /sweep --tests --prune to reduce prunable test count below threshold\n"
            f"\n"
            f"Steps:\n"
            f"1. Run: /sweep --tests --prune\n"
            f"2. Review the pruning recommendations\n"
            f"3. Remove or fix the flagged tests\n"
            f"4. Retry the commit\n"
            f"\n"
            f"To skip this check (not recommended): SKIP_PRUNABLE_GATE=1 git commit ...",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    _safe_main_953(main)
