#!/usr/bin/env python3
"""
Session Tracker - DEPRECATED - Use lib/session_tracker.py instead

DEPRECATION NOTICE (GitHub Issue #79):
=====================================================
This scripts/session_tracker.py is DEPRECATED and will be removed in v4.0.0.

The implementation has moved to plugins/autonomous-dev/lib/session_tracker.py
for portable path detection and better integration.

Migration:
- For CLI usage: Use plugins/autonomous-dev/scripts/session_tracker.py (installed plugin)
- For imports: Use plugins/autonomous_dev/lib/session_tracker import SessionTracker

This file remains temporarily for backward compatibility but delegates
to the lib implementation.

Date: 2025-11-19
Issue: GitHub #79 (Tracking infrastructure portability)
=====================================================

Session Tracker - Prevents context bloat
Logs agent actions to file instead of keeping in context

Usage:
    python scripts/session_tracker.py <agent_name> <message>

Example:
    python scripts/session_tracker.py researcher "Research complete - docs/research/auth.md"
"""

import sys
import warnings
from pathlib import Path

# Show deprecation warning when used as CLI
if __name__ == "__main__":
    warnings.warn(
        "\n"
        "scripts/session_tracker.py is DEPRECATED (GitHub Issue #79)\n"
        "Use plugins/autonomous-dev/scripts/session_tracker.py instead\n"
        "This file will be removed in v4.0.0\n",
        DeprecationWarning,
        stacklevel=2
    )

# Add project root to path for plugins import
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Delegate to lib implementation
from plugins.autonomous_dev.lib.session_tracker import main

if __name__ == "__main__":
    main()
