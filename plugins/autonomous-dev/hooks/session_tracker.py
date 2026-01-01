#!/usr/bin/env -S uv run --script --quiet --no-project
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session Tracker - Prevents context bloat
Logs agent actions to file instead of keeping in context

This hook is invoked by SubagentStop lifecycle to track agent completion.
Prevents context bloat by storing action logs in docs/sessions/ instead of conversation.

Usage (Hook):
    Configured in .claude/settings.local.json SubagentStop hook:
    python plugins/autonomous-dev/hooks/session_tracker.py <agent_name> <message>

Usage (CLI):
    python plugins/autonomous-dev/hooks/session_tracker.py researcher "Research complete - docs/research/auth.md"

Examples:
    # Hook invocation (automatic)
    python plugins/autonomous-dev/hooks/session_tracker.py researcher "Completed pattern research"

    # CLI invocation (manual)
    python plugins/autonomous-dev/hooks/session_tracker.py implementer "Code implementation done"

See Also:
    - docs/STRICT-MODE.md: SubagentStop hook configuration
    - CHANGELOG.md: Issue #84 - Hook path fixes
"""

import sys
import os
from datetime import datetime
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


class SessionTracker:
    def __init__(self):
        self.session_dir = Path("docs/sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Find or create session file for today
        today = datetime.now().strftime("%Y%m%d")
        session_files = list(self.session_dir.glob(f"{today}-*.md"))

        if session_files:
            # Use most recent session file from today
            self.session_file = sorted(session_files)[-1]
        else:
            # Create new session file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.session_file = self.session_dir / f"{timestamp}-session.md"

            # Initialize with header
            self.session_file.write_text(
                f"# Session {timestamp}\n\n"
                f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"---\n\n"
            )

    def log(self, agent_name, message):
        """Log agent action to session file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"**{timestamp} - {agent_name}**: {message}\n\n"

        # Append to session file
        with open(self.session_file, "a") as f:
            f.write(entry)

        # Print confirmation
        print(f"✅ Logged: {agent_name} - {message}")
        print(f"📄 Session: {self.session_file.name}")


def main():
    if len(sys.argv) < 3:
        print("Usage: session_tracker.py <agent_name> <message>")
        print("\nExample:")
        print('  session_tracker.py researcher "Research complete - docs/research/auth.md"')
        sys.exit(1)

    tracker = SessionTracker()
    agent_name = sys.argv[1]
    message = " ".join(sys.argv[2:])
    tracker.log(agent_name, message)


def track_agent_event(agent_name: str, message: str):
    """Track an agent event (wrapper for SessionTracker.log)."""
    tracker = SessionTracker()
    tracker.log(agent_name, message)


if __name__ == "__main__":
    main()
