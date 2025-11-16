# Retry Logic with Exponential Backoff

Automatically retry failed API calls with increasing delays.

## Pattern

```python
import time

def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s, ...
            time.sleep(delay)
```

## When to Use

- Network requests (transient failures)
- API rate limiting
- Database connections
- File operations on shared storage

See: `templates/retry-decorator-template.py`
