#!/usr/bin/env python3
"""
Alert when 100+ lines of code remain uncommitted.

This hook warns developers when uncommitted changes exceed a threshold
(default: 100 lines). Encourages regular commits and prevents loss of work.

Hook Type: PreSubagent
Trigger: Before subagent starts
Condition: Uncommitted changes exceed threshold
Action: Warn user but allow continuation (non-blocking)

Exit Codes:
  - EXIT_SUCCESS (0): No alert needed (<100 lines uncommitted)
  - EXIT_WARNING (2): 100+ lines uncommitted (warning only, non-blocking)

Environment Variables:
  - UNCOMMITTED_THRESHOLD: Custom threshold (default: 100)
  - DISABLE_UNCOMMITTED_ALERT: Set to "true" to disable alert

Lifecycle: PreSubagent
Author: implementer agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from subprocess import TimeoutExpired

# Import exit codes
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
try:
    from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING
except ImportError:
    EXIT_SUCCESS = 0
    EXIT_WARNING = 2

# Default threshold for uncommitted lines
DEFAULT_THRESHOLD = 100


def get_uncommitted_changes_count() -> int:
    """
    Get count of uncommitted lines using git diff --stat.

    Returns:
        Total number of uncommitted lines (insertions + deletions)
    """
    try:
        # Get staged and unstaged changes
        result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return 0

        return parse_git_diff_stat(result.stdout)

    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        return 0
    except Exception:
        return 0


def parse_git_diff_stat(output: str) -> int:
    """
    Parse git diff --stat output for total lines changed.

    Args:
        output: git diff --stat output

    Returns:
        Total lines changed (insertions + deletions)

    Examples:
        >>> parse_git_diff_stat(" file1.py | 20 +++++++++++++++++")
        20
        >>> parse_git_diff_stat(" file1.py | 20 +++++++++++++++++\\n file2.py | 30 ---------------")
        50
    """
    total = 0

    for line in output.strip().splitlines():
        # Skip summary line like "2 files changed, 35 insertions(+)"
        if "files changed" in line or "file changed" in line:
            continue

        # Skip binary files like "binary.bin | Bin 0 -> 1024 bytes"
        if "Bin " in line:
            continue

        # Parse file line like " file1.py | 20 ++++++++++++++++++---------"
        # Format: " filename | count symbols"
        match = re.search(r'\|\s*(\d+)\s+[+\-]+', line)
        if match:
            count = int(match.group(1))
            total += count

    return total


def should_alert_uncommitted(line_count: int, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """
    Return True if line count exceeds threshold.

    Args:
        line_count: Number of uncommitted lines
        threshold: Threshold for alert (default: 100)

    Returns:
        True if alert should be shown
    """
    return line_count >= threshold


def format_alert_message(line_count: int, threshold: int = DEFAULT_THRESHOLD) -> str:
    """
    Format warning message for uncommitted changes.

    Args:
        line_count: Number of uncommitted lines
        threshold: Threshold for alert

    Returns:
        Formatted alert message
    """
    return (
        f"⚠️  {line_count} uncommitted lines detected (threshold: {threshold}). "
        f"Consider committing your changes."
    )


def run_hook() -> int:
    """
    Main hook logic.

    Returns:
        EXIT_SUCCESS or EXIT_WARNING
    """
    # Check if alert is disabled
    if os.environ.get("DISABLE_UNCOMMITTED_ALERT", "").lower() == "true":
        return EXIT_SUCCESS

    # Get threshold from environment or use default
    try:
        threshold = int(os.environ.get("UNCOMMITTED_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        threshold = DEFAULT_THRESHOLD

    # Get uncommitted changes count
    try:
        line_count = get_uncommitted_changes_count()
    except Exception:
        # If we can't get git status, don't block
        return EXIT_SUCCESS

    # Check if alert needed
    if should_alert_uncommitted(line_count, threshold):
        message = format_alert_message(line_count, threshold)
        print(message)
        return EXIT_WARNING

    return EXIT_SUCCESS


def main():
    """Entry point."""
    sys.exit(run_hook())


if __name__ == "__main__":
    main()
