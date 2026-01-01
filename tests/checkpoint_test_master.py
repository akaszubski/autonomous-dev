#!/usr/bin/env python3
"""
Checkpoint tracker for test-master agent - Issue #183

Saves agent checkpoint for AI-powered merge conflict resolution tests.
"""

from pathlib import Path
import sys

# Portable path detection (works from any directory)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

# Add lib to path for imports
lib_path = project_root / "plugins/autonomous-dev/lib"
if lib_path.exists():
    sys.path.insert(0, str(lib_path))

    try:
        from agent_tracker import AgentTracker
        AgentTracker.save_agent_checkpoint(
            'test-master',
            'TDD Red Phase Complete - 27 tests created for conflict_resolver (Issue #183)'
        )
        print("✅ Checkpoint saved - 27 conflict_resolver tests created")
    except ImportError:
        print("ℹ️ Checkpoint skipped (user project)")
else:
    print("ℹ️ Checkpoint skipped (lib not found)")
