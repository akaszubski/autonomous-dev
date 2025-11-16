# File Locking Patterns

Prevent concurrent modification using file locks.

## Pattern

Use `fcntl.flock()` for exclusive locks:

```python
import fcntl

with open(state_file, 'r+') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        # Modify file exclusively
        pass
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

See: `templates/file-lock-template.py`
