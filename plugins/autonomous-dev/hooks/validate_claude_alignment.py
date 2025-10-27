#!/usr/bin/env python3
"""
Pre-commit hook: Validate CLAUDE.md alignment.

Ensures CLAUDE.md stays in sync with actual codebase (PROJECT.md, agents,
commands, hooks). Detects drift and warns Claude to fix documentation.

Exit codes:
- 0: Aligned, commit proceeds
- 1: Drift detected, warning shown (Claude can fix and re-commit)
- 2: Critical misalignment (commit blocked, urgent fix needed)

This hook runs BEFORE every commit to prevent documentation drift.
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Set


class SessionWarningTracker:
    """Track warnings shown per session to avoid spam."""

    def __init__(self, session_id: Optional[str] = None):
        """Initialize tracker."""
        self.session_id = session_id or "default"
        self.state_file = Path.home() / ".claude" / f"_validation_state_{self.session_id}.json"

    def has_shown_warning(self, warning_key: str) -> bool:
        """Check if warning was already shown this session."""
        if not self.state_file.exists():
            return False
        data = json.loads(self.state_file.read_text())
        return warning_key in data.get("shown_warnings", [])

    def mark_warning_shown(self, warning_key: str):
        """Mark warning as shown this session."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
        else:
            data = {"shown_warnings": []}
        data["shown_warnings"].append(warning_key)
        self.state_file.write_text(json.dumps(data))


def validate_claude_alignment() -> tuple[bool, List[str]]:
    """
    Validate CLAUDE.md alignment.

    Returns:
        (is_aligned, issues) - is_aligned is True if all checks pass
    """
    issues = []

    # Get repo root (where .git is)
    repo_root = Path.cwd()
    while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
        repo_root = repo_root.parent

    # Read CLAUDE.md files
    project_claude_path = repo_root / "CLAUDE.md"
    project_md_path = repo_root / ".claude" / "PROJECT.md"

    if not project_claude_path.exists():
        return True, []  # No CLAUDE.md = skip check

    project_claude = project_claude_path.read_text()
    if not project_md_path.exists():
        return True, []  # No PROJECT.md = skip check

    project_md = project_md_path.read_text()

    # Check 1: Version consistency
    project_claude_date = extract_date(project_claude)
    project_md_date = extract_date(project_md)

    if project_claude_date and project_md_date:
        if project_claude_date < project_md_date:
            issues.append(
                "Project CLAUDE.md is outdated (older than PROJECT.md). "
                "Run: python plugins/autonomous-dev/scripts/validate_claude_alignment.py"
            )

    # Check 2: Agent count
    actual_agents = len(list((repo_root / "plugins/autonomous-dev/agents").glob("*.md")))
    documented_agents = extract_agent_count(project_claude)

    if documented_agents and documented_agents != actual_agents:
        issues.append(
            f"Agent count drift: CLAUDE.md says {documented_agents}, but {actual_agents} exist. "
            "Update CLAUDE.md line with: ### Agents ({actual_agents} specialists)"
        )

    # Check 3: Command count
    actual_commands = len(list((repo_root / "plugins/autonomous-dev/commands").glob("*.md")))
    documented_commands = extract_command_count(project_claude)

    if documented_commands and documented_commands != actual_commands:
        issues.append(
            f"Command count drift: CLAUDE.md says {documented_commands}, but {actual_commands} exist. "
            f"Update CLAUDE.md with correct count."
        )

    # Check 4: Key commands exist
    required_commands = [
        "auto-implement", "align-project", "setup", "test",
        "status", "health-check", "sync-dev", "uninstall"
    ]
    missing_commands = []

    for cmd in required_commands:
        if not (repo_root / "plugins/autonomous-dev/commands" / f"{cmd}.md").exists():
            missing_commands.append(cmd)

    if missing_commands:
        issues.append(
            f"Missing documented commands: {', '.join(missing_commands)}. "
            "CLAUDE.md references commands that don't exist."
        )

    # Return results
    has_errors = bool(missing_commands)  # Missing commands = error
    is_aligned = not has_errors

    return is_aligned, issues


def extract_date(text: str) -> Optional[str]:
    """Extract date from text."""
    match = re.search(r"Last Updated['\"]?\s*:\s*(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else None


def extract_agent_count(text: str) -> Optional[int]:
    """Extract agent count from text."""
    match = re.search(r"### Agents \((\d+)", text)
    return int(match.group(1)) if match else None


def extract_command_count(text: str) -> Optional[int]:
    """Extract command count from text."""
    match = re.search(r"Done! All commands work: .*?\(.*?(\d+) commands?\)", text)
    if not match:
        match = re.search(r"(\d+) total\s+commands", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def main():
    """Run validation hook."""
    is_aligned, issues = validate_claude_alignment()

    if not issues:
        sys.exit(0)  # All good, silent success

    # Track warnings to avoid spam
    tracker = SessionWarningTracker()

    # Show warnings
    for issue in issues:
        warning_key = issue.split(".")[0]  # Use first sentence as key
        if not tracker.has_shown_warning(warning_key):
            print(f"⚠️  CLAUDE.md Alignment: {issue}", file=sys.stderr)
            tracker.mark_warning_shown(warning_key)

    # Exit code depends on severity
    if any("Missing" in issue for issue in issues):
        sys.exit(2)  # Critical (blocks commit)
    else:
        sys.exit(1)  # Warnings (commit proceeds, Claude sees warning)


if __name__ == "__main__":
    main()
