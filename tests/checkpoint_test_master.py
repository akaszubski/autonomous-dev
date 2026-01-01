#!/usr/bin/env python3
"""
Checkpoint tracker for test-master agent - Issue #176

Saves agent checkpoint for headless mode tests.
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
            'Tests complete - 53 tests created for headless mode CI/CD integration (Issue #176)'
        )
        print("✅ Checkpoint saved - 53 headless mode tests created")
    except ImportError:
        print("ℹ️ Checkpoint skipped (user project)")
else:
    print("ℹ️ Checkpoint skipped (lib not found)")
