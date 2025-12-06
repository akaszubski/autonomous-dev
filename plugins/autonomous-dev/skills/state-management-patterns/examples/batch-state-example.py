#!/usr/bin/env python3
"""Batch state management example from BatchStateManager.

See: plugins/autonomous-dev/lib/batch_state_manager.py
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
import json
import tempfile
import os
from datetime import datetime


@dataclass
class BatchState:
    """Example batch state with crash recovery."""
    batch_id: str
    features: List[str]
    current_index: int = 0
    completed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    context_clears: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def create(cls, features: List[str]) -> 'BatchState':
        """Create new batch state."""
        batch_id = f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        return cls(batch_id=batch_id, features=features)

    def save(self, state_dir: Path = None) -> None:
        """Save with atomic write.
        
        Note: In production, use get_batch_state_file() from path_utils
        for portable path detection (Issue #79, #85).
        """
        if state_dir is None:
            # For this example, use hardcoded fallback
            # In production, use: from path_utils import get_batch_state_file
            state_dir = Path(".claude/batch_state.json")
        temp_fd, temp_path = tempfile.mkstemp(dir=state_dir.parent)
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(temp_path, state_dir)
        except:
            Path(temp_path).unlink()
            raise

    def get_next(self) -> Optional[str]:
        """Get next feature (resume support)."""
        while self.current_index < len(self.features):
            feat = self.features[self.current_index]
            if feat not in self.completed:
                return feat
            self.current_index += 1
        return None


# Usage example
if __name__ == "__main__":
    # Create batch
    state = BatchState.create(["feat1", "feat2", "feat3"])
    print(f"Batch ID: {state.batch_id}")

    # Process features
    while (feat := state.get_next()):
        print(f"Processing: {feat}")
        # ... process ...
        state.completed.append(feat)
        state.current_index += 1
        state.save()  # Save after each feature

    print(f"Completed: {len(state.completed)}/{len(state.features)}")
