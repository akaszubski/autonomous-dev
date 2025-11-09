#!/usr/bin/env python3
"""
Health check script - validates plugin integrity.

This script provides health check functionality for the autonomous-dev plugin.
Re-exports PluginHealthCheck from hooks/health_check.py for backward compatibility.
"""

import sys
from pathlib import Path
import importlib.util

# Import PluginHealthCheck from hooks/health_check.py using direct file import
hooks_health_check_path = Path(__file__).parent.parent / 'hooks' / 'health_check.py'
spec = importlib.util.spec_from_file_location("hooks_health_check", hooks_health_check_path)
hooks_health_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks_health_check)

# Re-export PluginHealthCheck
PluginHealthCheck = hooks_health_check.PluginHealthCheck


def main():
    """Run health check on plugin."""
    try:
        checker = PluginHealthCheck()
        checker.run()
        return 0
    except Exception as e:
        print(f"Health check failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
