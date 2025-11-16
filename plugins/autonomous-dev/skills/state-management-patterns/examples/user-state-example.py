#!/usr/bin/env python3
"""User state management example from UserStateManager.

See: plugins/autonomous-dev/lib/user_state_manager.py
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import tempfile
import os


@dataclass
class UserState:
    """Example user preferences state."""
    git_auto_enabled: bool = True
    git_auto_push: bool = True
    git_auto_pr: bool = True
    first_run_complete: bool = False

    @classmethod
    def load_or_create(cls, state_file: Path = Path("~/.autonomous-dev/user_state.json")) -> 'UserState':
        """Load existing or create default state."""
        state_file = state_file.expanduser()
        if state_file.exists():
            with state_file.open('r') as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save(self, state_file: Path = Path("~/.autonomous-dev/user_state.json")) -> None:
        """Save with atomic write."""
        state_file = state_file.expanduser()
        state_file.parent.mkdir(parents=True, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(dir=state_file.parent)
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(temp_path, state_file)
        except:
            Path(temp_path).unlink()
            raise


# Usage example
if __name__ == "__main__":
    state = UserState.load_or_create()
    print(f"Git auto-enabled: {state.git_auto_enabled}")

    # Update preference
    state.git_auto_enabled = False
    state.save()
    print("Preferences saved")
