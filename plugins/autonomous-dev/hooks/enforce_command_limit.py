#!/usr/bin/env python3
"""Enforce 8-command limit.

Blocks commits if more than 8 active commands exist.
Allowed commands: auto-implement, align-project, setup, test, status, health-check, sync-dev, uninstall
"""

import subprocess
import sys
from pathlib import Path


ALLOWED_COMMANDS = {
    "auto-implement",
    "align-project",
    "setup",
    "test",
    "status",
    "health-check",
    "sync-dev",
    "uninstall",
}


def main():
    """Check command count."""
    commands_dir = Path("./plugins/autonomous-dev/commands")
    if not commands_dir.exists():
        sys.exit(0)

    # Find all active commands (not in archive)
    active = [
        f.stem
        for f in commands_dir.glob("*.md")
        if not f.parent.name == "archive"
    ]

    if len(active) > 8:
        disallowed = set(active) - ALLOWED_COMMANDS
        print(f"❌ Too many commands: {len(active)} active (limit: 8)", file=sys.stderr)
        print(f"\nAllowed 8 commands:", file=sys.stderr)
        for cmd in sorted(ALLOWED_COMMANDS):
            marker = "✓" if cmd in active else " "
            print(f"  [{marker}] {cmd}", file=sys.stderr)

        if disallowed:
            print(f"\nDisallowed commands (archive these):", file=sys.stderr)
            for cmd in sorted(disallowed):
                print(f"  ❌ {cmd}.md → move to archive/", file=sys.stderr)

        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
