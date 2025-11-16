#!/usr/bin/env python3
"""State manager template with JSON persistence, atomic writes, and crash recovery.

See: skills/state-management-patterns
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import tempfile
import os
from datetime import datetime


@dataclass
class StateManager:
    """Template for state management with persistence.

    See skills/state-management-patterns for full documentation.
    """
    state_id: str
    items: List[str]
    current_index: int = 0
    completed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"

    @classmethod
    def create(cls, items: List[str], state_id: Optional[str] = None) -> 'StateManager':
        """Create new state."""
        if not state_id:
            state_id = f"state-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        return cls(state_id=state_id, items=items)

    @classmethod
    def load(cls, state_id: str, state_dir: Path = Path(".state")) -> 'StateManager':
        """Load existing state from JSON."""
        state_file = state_dir / f"{state_id}.json"
        with state_file.open('r') as f:
            data = json.load(f)
        return cls(**data)

    def save(self, state_dir: Path = Path(".state")) -> None:
        """Save state with atomic write."""
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / f"{self.state_id}.json"

        self.last_updated = datetime.now().isoformat()

        # Atomic write pattern
        temp_fd, temp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(temp_path, state_file)
        except Exception:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    def get_next(self) -> Optional[str]:
        """Get next item to process (skips completed)."""
        while self.current_index < len(self.items):
            item = self.items[self.current_index]
            if item not in self.completed:
                return item
            self.current_index += 1
        return None

    def mark_completed(self, item: str) -> None:
        """Mark item as completed."""
        if item not in self.completed:
            self.completed.append(item)

    def mark_failed(self, item: str, error: str = "") -> None:
        """Mark item as failed."""
        if item not in self.failed:
            self.failed.append(item)
