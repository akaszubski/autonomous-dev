# Monitoring Metrics

## Stack Traces

### Print Stack Trace

```python
import traceback

try:
    risky_operation()
except Exception as e:
    traceback.print_exc()  # Print stack trace to stderr
```

**Capture to string**:
```python
import traceback

try:
    risky_operation()
except Exception as e:
    trace = traceback.format_exc()
    logger.error(f"Error occurred: {trace}")
```

---

### Rich Tracebacks (rich)

**Beautiful, informative tracebacks**:

```bash
pip install rich
```

```python
from rich.traceback import install
install(show_locals=True)

def buggy_function():
    x = 42
    y = None
    return x + y  # TypeError with beautiful traceback

buggy_function()
```

**Shows**:
- ✅ Syntax highlighted code
- ✅ Local variables at each frame
- ✅ Clear error message

---

## Performance Monitoring

### Timing Decorator

**Measure function execution time**:

```python
import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()

        duration = end - start
        print(f"{func.__name__} took {duration:.4f}s")

        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "done"

slow_function()
# Output: slow_function took 1.0001s
```

---

### Context Manager Timer

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name):
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    print(f"{name} took {end - start:.4f}s")

# Usage
with timer("Database query"):
    result = db.query(...)

with timer("File processing"):
    process_file(path)
```

---

### Performance Assertions

**Fail if too slow**:

```python
import time

def performance_test():
    start = time.perf_counter()

    # Your code
    process_data()

    duration = time.perf_counter() - start
    assert duration < 0.1, f"Too slow: {duration:.4f}s"
```

---
