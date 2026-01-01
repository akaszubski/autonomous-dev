#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Shim for deprecated auto_git_workflow.py - redirects to unified_git_automation.py

This file exists for backward compatibility with cached settings or configurations
that still reference the old hook name after consolidation (Issue #144).

The actual implementation is in unified_git_automation.py.
"""
import os
import subprocess
import sys
from pathlib import Path


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ
# Fallback for non-UV environments (placeholder - this hook doesn't use lib imports)
if not is_running_under_uv():
    # This hook doesn't import from autonomous-dev/lib
    # But we keep sys.path.insert() for test compatibility
    from pathlib import Path
    import sys
    hook_dir = Path(__file__).parent
    lib_path = hook_dir.parent / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))


def main():
    """Run the unified git automation hook."""
    # Get the directory where this script lives
    hook_dir = Path(__file__).parent

    # Call the unified hook with the same arguments
    unified_hook = hook_dir / "unified_git_automation.py"

    if unified_hook.exists():
        result = subprocess.run(
            [sys.executable, str(unified_hook)] + sys.argv[1:],
            capture_output=False,
        )
        sys.exit(result.returncode)
    else:
        print(f"WARNING: unified_git_automation.py not found at {unified_hook}", file=sys.stderr)
        sys.exit(0)  # Non-blocking - don't fail the workflow


if __name__ == "__main__":
    main()
