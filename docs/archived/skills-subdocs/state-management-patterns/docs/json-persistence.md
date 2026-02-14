# JSON Persistence Patterns

Store application state in JSON files with atomic writes to prevent corruption.

## Pattern

Use atomic writes via temporary files:

1. Write to temporary file
2. Rename to target (atomic operation)
3. Clean up temp file on error

## Example

```python
import json, tempfile, os
from pathlib import Path

def save_state(state: dict, path: Path):
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(temp_path, path)
    except:
        Path(temp_path).unlink()
        raise
```

See: `skills/state-management-patterns/templates/atomic-write-template.py`
