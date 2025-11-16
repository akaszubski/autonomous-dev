#!/usr/bin/env python3
"""File locking template for concurrent access protection.

See: skills/state-management-patterns/docs/file-locking.md
"""

import fcntl
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict


@contextmanager
def file_lock(filepath: Path):
    """Acquire exclusive file lock.

    Args:
        filepath: File to lock

    Yields:
        Open file handle with exclusive lock

    Example:
        >>> with file_lock(Path("state.json")) as f:
        ...     state = json.load(f)
        ...     state['count'] += 1
        ...     f.seek(0)
        ...     f.truncate()
        ...     json.dump(state, f)
    """
    with filepath.open('r+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def update_state_locked(filepath: Path, updates: Dict[str, Any]) -> None:
    """Update state file with file locking.

    Args:
        filepath: State file path
        updates: Updates to apply

    Example:
        >>> update_state_locked(Path("state.json"), {"count": 42})
    """
    if not filepath.exists():
        filepath.write_text(json.dumps({}))

    with file_lock(filepath) as f:
        state = json.load(f)
        state.update(updates)
        f.seek(0)
        f.truncate()
        json.dump(state, f, indent=2)
