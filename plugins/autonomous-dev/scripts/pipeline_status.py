#!/usr/bin/env python3
"""
Pipeline status script - displays current /auto-implement workflow status.

Shows agent progress, current step, and estimated completion.
"""

import sys
from pathlib import Path

# Add scripts to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from pipeline_controller import PipelineController


def main():
    """Display current pipeline status."""
    # Find latest session file
    sessions_dir = Path.cwd() / "docs" / "sessions"
    if not sessions_dir.exists():
        print("No session directory found")
        return 1

    # Get most recent session JSON
    session_files = list(sessions_dir.glob("*.json"))
    if not session_files:
        print("No active pipeline sessions found")
        return 0

    latest_session = max(session_files, key=lambda p: p.stat().st_mtime)

    # Create controller and display status
    controller = PipelineController(session_file=latest_session)

    try:
        # This would normally start the display, but for status check
        # we just want to show current state
        print(f"Pipeline session: {latest_session.name}")
        print("Status: Running" if controller.display_process else "Status: No active display")
        return 0
    except Exception as e:
        print(f"Error checking pipeline status: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
