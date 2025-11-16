#!/usr/bin/env python3
"""Crash recovery demonstration.

Shows how state enables recovery after crashes.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
import json
import sys


@dataclass
class RecoverableTask:
    """Task with crash recovery support."""
    task_id: str
    items: List[str]
    current_index: int = 0
    completed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Save state."""
        with path.open('w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> 'RecoverableTask':
        """Load state."""
        with path.open('r') as f:
            return cls(**json.load(f))

    def get_next(self) -> Optional[str]:
        """Get next item (skips completed)."""
        while self.current_index < len(self.items):
            item = self.items[self.current_index]
            if item not in self.completed and item not in self.failed:
                return item
            self.current_index += 1
        return None

    def process(self, state_file: Path) -> None:
        """Process items with crash recovery."""
        while (item := self.get_next()):
            print(f"Processing: {item}")

            try:
                # Simulate work
                if item == "crash":
                    raise RuntimeError("Simulated crash!")

                # Mark completed
                self.completed.append(item)
                self.current_index += 1

            except Exception as e:
                print(f"Error: {e}")
                self.failed.append(item)
                self.current_index += 1

            # Save after each item (enables recovery)
            self.save(state_file)
            print(f"  Saved state (completed: {len(self.completed)})")


# Demonstration
if __name__ == "__main__":
    state_file = Path(".task_state.json")

    if state_file.exists():
        # Resume from crash
        print("Resuming from saved state...")
        task = RecoverableTask.load(state_file)
    else:
        # New task
        print("Starting new task...")
        task = RecoverableTask(
            task_id="demo",
            items=["item1", "item2", "crash", "item3", "item4"]
        )

    # Process (will crash on "crash" item)
    task.process(state_file)

    # Summary
    print(f"\nCompleted: {task.completed}")
    print(f"Failed: {task.failed}")
    print(f"\nTo resume after crash: python {__file__}")
