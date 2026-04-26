#!/usr/bin/env python3
"""
PreCommit hook: Enforce regression tests on bug fix commits.

Blocks commits with fix:/bugfix:/hotfix: prefixes when no test files
are staged. Follows the stick+carrot pattern with REQUIRED NEXT ACTION.

Issue #737: Enforce regression tests on all behavior fixes.
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


# Fallback for non-UV environments — add lib to sys.path
if not is_running_under_uv():
    hook_dir = Path(__file__).resolve().parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
    # Also try the installed location
    installed_lib = hook_dir.parent.parent / "lib"
    if installed_lib.exists():
        sys.path.insert(0, str(installed_lib))

# Import from shared bugfix detector library
try:
    from bugfix_detector import is_bugfix_commit
except ImportError:
    # If the library is not available, allow the commit (graceful degradation)
    sys.exit(0)


def get_commit_message() -> str:
    """Read the commit message from .git/COMMIT_EDITMSG.

    Returns:
        The commit message text, or empty string if not readable.
    """
    # Find the git directory
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        git_dir = Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return ""

    commit_msg_file = git_dir / "COMMIT_EDITMSG"
    if not commit_msg_file.exists():
        return ""

    try:
        return commit_msg_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def get_staged_files() -> list[str]:
    """Get the list of staged file paths.

    Returns:
        List of staged file paths relative to repo root.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


def has_test_files(staged_files: list[str]) -> bool:
    """Check if any staged files are test files.

    A file is considered a test file if:
    - Its name contains 'test_' or ends with '_test.py'
    - It is under a 'tests/' directory

    Args:
        staged_files: List of staged file paths.

    Returns:
        True if at least one staged file is a test file.
    """
    for filepath in staged_files:
        basename = Path(filepath).name
        # Check filename patterns
        if "test_" in basename or basename.endswith("_test.py"):
            return True
        # Check if under tests/ directory
        if filepath.startswith("tests/") or "/tests/" in filepath:
            return True
    return False


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        0 to allow the commit, 2 to block it.
    """
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="git-commit")
            return 0
    except ImportError:
        pass

    message = get_commit_message()
    if not message:
        return 0

    if not is_bugfix_commit(message):
        return 0

    staged_files = get_staged_files()
    if has_test_files(staged_files):
        return 0

    # Block: bug fix commit without regression test
    first_line = message.strip().split("\n")[0]
    print(
        f'BLOCKED: Bug fix commit requires regression test.\n'
        f'\n'
        f'Commit message "{first_line}" detected but no test files in staged changes.\n'
        f'\n'
        f'REQUIRED NEXT ACTION:\n'
        f'1. Add a test that fails without your fix and passes with it\n'
        f'2. Stage the test file: git add tests/...\n'
        f'3. Retry the commit\n'
        f'\n'
        f'Exception: If an EXISTING test already covers this regression,\n'
        f'add --no-verify and document which test covers it in the commit body.',
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    _safe_main_953(main)
