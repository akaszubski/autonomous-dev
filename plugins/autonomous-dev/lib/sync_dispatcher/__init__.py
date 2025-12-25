#!/usr/bin/env python3
"""
Sync Dispatcher Package - Unified sync operations dispatcher

This package provides sync dispatch functionality organized into focused modules:
- models: Data structures (SyncResult, exceptions)
- modes: Mode-specific dispatch functions
- dispatcher: Main SyncDispatcher class
- cli: CLI interface and convenience functions

All public symbols are re-exported from this __init__.py for backward compatibility.

Usage:
    # Old import paths still work
    from sync_dispatcher import SyncResult, SyncDispatcher, dispatch_sync

    # New package paths also work
    from sync_dispatcher.models import SyncResult
    from sync_dispatcher.dispatcher import SyncDispatcher
    from sync_dispatcher.cli import dispatch_sync

Date: 2025-12-25
Issue: GitHub #TBD - Refactor sync_dispatcher into package
"""

# Re-export all public symbols for backward compatibility
# Using "from .module import Symbol as Symbol" pattern to satisfy type checkers

# From models.py
from .models import SyncResult as SyncResult
from .models import SyncDispatcherError as SyncDispatcherError
from .models import SyncError as SyncError

# From dispatcher.py
from .dispatcher import SyncDispatcher as SyncDispatcher
from .dispatcher import AgentInvoker as AgentInvoker

# From cli.py
from .cli import dispatch_sync as dispatch_sync
from .cli import sync_marketplace as sync_marketplace
from .cli import main as main

# Re-export SyncMode for backward compatibility
# (Some tests import it from here even though it's from sync_mode_detector)
try:
    from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode as SyncMode
except ImportError:
    from sync_mode_detector import SyncMode as SyncMode  # type: ignore

# Define __all__ for explicit exports
__all__ = [
    # Models
    "SyncResult",
    "SyncDispatcherError",
    "SyncError",
    # Dispatcher
    "SyncDispatcher",
    # CLI
    "dispatch_sync",
    "sync_marketplace",
    "main",
    "AgentInvoker",
    # Re-exported for backward compatibility
    "SyncMode",
]
