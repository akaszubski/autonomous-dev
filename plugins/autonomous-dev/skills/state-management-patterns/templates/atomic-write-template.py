#!/usr/bin/env python3
"""Atomic write template for safe file persistence.

See: skills/state-management-patterns/docs/atomic-writes.md
"""

import json
import tempfile
import os
from pathlib import Path
from typing import Any, Dict


def save_json_atomic(data: Dict[str, Any], filepath: Path) -> None:
    """Save JSON data with atomic write to prevent corruption.

    Args:
        data: Data to save
        filepath: Target file path

    Example:
        >>> save_json_atomic({"key": "value"}, Path("state.json"))
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp"
    )

    try:
        # Write JSON
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(data, f, indent=2)

        # Atomic rename (overwrites target)
        os.replace(temp_path, filepath)

    except Exception:
        # Clean up temp file on error
        if Path(temp_path).exists():
            Path(temp_path).unlink()
        raise
