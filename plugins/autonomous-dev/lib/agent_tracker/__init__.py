#!/usr/bin/env python3
"""
Agent Tracker Package - Refactored agent tracking with modular architecture

This package provides agent pipeline tracking functionality organized into focused modules:
- models: Constants and metadata (AGENT_METADATA, EXPECTED_AGENTS)
- state: Session state management and agent lifecycle
- metrics: Progress calculation and time estimation
- verification: Parallel execution verification
- display: Status display and visualization
- tracker: Main AgentTracker class coordinating all functionality
- cli: Command-line interface

All public symbols are re-exported from this __init__.py for backward compatibility.

Usage:
    # Old import paths still work (backward compatible)
    from agent_tracker import AgentTracker, AGENT_METADATA, EXPECTED_AGENTS

    # New package paths also work
    from agent_tracker.tracker import AgentTracker
    from agent_tracker.models import AGENT_METADATA, EXPECTED_AGENTS
    from agent_tracker.state import StateManager
    from agent_tracker.metrics import MetricsCalculator
    from agent_tracker.verification import ParallelVerifier
    from agent_tracker.display import DisplayFormatter
    from agent_tracker.cli import main

Date: 2025-12-25
Issue: GitHub #165 - Refactor agent_tracker.py into package
"""

# Re-export all public symbols for backward compatibility
# Using "from .module import Symbol as Symbol" pattern to satisfy type checkers

# From models.py
from .models import AGENT_METADATA as AGENT_METADATA
from .models import EXPECTED_AGENTS as EXPECTED_AGENTS

# From tracker.py
from .tracker import AgentTracker as AgentTracker

# From cli.py
from .cli import main as main

# Re-export path utilities for backward compatibility
# These were previously exported from the monolithic file
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_utils import get_project_root as get_project_root
from path_utils import find_project_root as find_project_root

# Version
__version__ = "2.0.0"

# Define explicit exports
__all__ = [
    # Core classes
    "AgentTracker",

    # Constants
    "AGENT_METADATA",
    "EXPECTED_AGENTS",

    # Path utilities (re-exported for backward compatibility)
    "get_project_root",
    "find_project_root",

    # CLI
    "main",
]
