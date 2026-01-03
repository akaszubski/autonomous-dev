"""
Pytest configuration for autonomous-dev plugin tests.

Adds the lib directory to sys.path so tests can import modules directly.
"""

import sys
from pathlib import Path

# Add lib directory to path
lib_path = Path(__file__).parent.parent / "lib"
if lib_path.exists() and str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))
