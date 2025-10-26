---
name: observability
type: knowledge
description: Logging, debugging, profiling, and performance monitoring for development. Use when adding logging, debugging issues, profiling performance, or instrumenting code for observability.
keywords: logging, debug, debugger, pdb, profiling, performance, trace, stack trace, logger, log level, metrics, monitoring
auto_activate: true
---

# Observability Skill

Developer-focused observability: logging, debugging, profiling, and performance monitoring.

## When This Skill Activates

- Adding logging to code
- Debugging errors or issues
- Profiling performance bottlenecks
- Analyzing memory usage
- Adding instrumentation
- Setting up structured logging
- Keywords: "logging", "debug", "profiling", "performance", "trace"

---

## Structured Logging

### Why Structured Logging?

**Traditional (unstructured)**:
```python
print(f"User {user_id} logged in from {ip_address}")
# Hard to parse, search, filter
```

**Structured (JSON)**:
```python
logger.info("user_login", extra={
    "user_id": user_id,
    "ip_address": ip_address,
    "timestamp": datetime.utcnow().isoformat()
})
# Easy to parse, search, filter, aggregate
```

**Benefits**:
- ✅ Easy to search/filter
- ✅ Machine-readable
- ✅ Aggregate metrics
- ✅ Correlate events
- ✅ Feed to log aggregators (ELK, Splunk, Datadog)

---

### Python Logging Setup

**Basic configuration**:

```python
import logging
import sys

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console
        logging.FileHandler('app.log')      # File
    ]
)

logger = logging.getLogger(__name__)

# Use it
logger.info("Application started")
logger.warning("Database connection slow")
logger.error("Failed to process request", exc_info=True)
```

---

### Log Levels

| Level | Value | Use When | Example |
|-------|-------|----------|---------|
| **DEBUG** | 10 | Development, detailed tracing | Variable values, function calls |
| **INFO** | 20 | Normal operations | User logged in, request processed |
| **WARNING** | 30 | Unexpected but handled | Deprecated API used, slow query |
| **ERROR** | 40 | Error occurred | Failed to save file, API error |
| **CRITICAL** | 50 | System failure | Database down, disk full |

**Usage**:
```python
logger.debug(f"Processing item: {item}")           # Development only
logger.info(f"User {user_id} logged in")           # Normal event
logger.warning(f"Query took {duration}s (slow!)")  # Unexpected
logger.error(f"Failed to save: {error}")           # Error
logger.critical(f"Database unreachable!")          # System failure
```

---

### Structured JSON Logging

**Using python-json-logger**:

```python
from pythonjsonlogger import jsonlogger
import logging

# Setup JSON formatter
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s'
)
logHandler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Log with extra fields
logger.info("user_login", extra={
    "user_id": 123,
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
})
```

**Output**:
```json
{
  "asctime": "2025-10-24 12:00:00,000",
  "name": "root",
  "levelname": "INFO",
  "message": "user_login",
  "user_id": 123,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0..."
}
```

---

### Context Logging

**Add context to all logs in a function**:

```python
import logging
from contextvars import ContextVar

# Context variable
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

# Add filter
logger.addFilter(ContextFilter())

# Use in request handler
def handle_request(request):
    request_id = generate_request_id()
    request_id_var.set(request_id)

    logger.info("Processing request")  # Includes request_id automatically
    process_data()
    logger.info("Request complete")    # Includes request_id automatically
```

---

### Best Practices for Logging

**✅ DO**:

```python
# 1. Use appropriate log levels
logger.debug("Variable value: {value}")      # Debug details
logger.info("User action completed")         # Normal operations
logger.error("Failed to process", exc_info=True)  # Errors

# 2. Include context
logger.info("Processing payment", extra={
    "user_id": user_id,
    "amount": amount,
    "currency": currency
})

# 3. Log exceptions with stack traces
try:
    process_data()
except Exception as e:
    logger.error("Processing failed", exc_info=True)  # Includes stack trace

# 4. Use lazy formatting
logger.debug("Processing %s items", len(items))  # Only formats if DEBUG enabled
```

**❌ DON'T**:

```python
# 1. Don't log sensitive data
logger.info(f"User password: {password}")  # NEVER!
logger.info(f"Credit card: {card_number}")  # NEVER!

# 2. Don't log in loops (too verbose)
for item in items:
    logger.info(f"Processing {item}")  # 1M items = 1M log lines!

# 3. Don't use print() in production
print("Debug info")  # Use logger.debug() instead

# 4. Don't catch and ignore
try:
    process()
except:
    pass  # Silent failure! At least log it!
```

---

## Debugging

### Print Debugging

**Strategic print statements**:

```python
def process_data(data):
    print(f"[DEBUG] Input: {data}")  # See input

    result = transform(data)
    print(f"[DEBUG] After transform: {result}")  # See intermediate

    validated = validate(result)
    print(f"[DEBUG] After validate: {validated}")  # See output

    return validated
```

**Use temporary, remove before commit**:
```python
# ✅ GOOD: Temporary debug
print(f"[DEBUG] value={value}")  # Remove before commit

# ❌ BAD: Permanent debug prints
print("Processing...")  # Clutters output forever
```

---

### Interactive Debugger (pdb)

**Built-in Python debugger**:

```python
import pdb

def buggy_function(x, y):
    result = x + y
    pdb.set_trace()  # Debugger starts here
    return result * 2

# When debugger starts:
# (Pdb) p x          # Print variable x
# (Pdb) p y          # Print variable y
# (Pdb) p result     # Print result
# (Pdb) n            # Next line
# (Pdb) s            # Step into function
# (Pdb) c            # Continue execution
# (Pdb) q            # Quit debugger
```

**Breakpoint (Python 3.7+)**:
```python
def buggy_function(x, y):
    result = x + y
    breakpoint()  # Better than pdb.set_trace()
    return result * 2
```

---

### IPython Debugger (ipdb)

**Enhanced debugger with syntax highlighting**:

```bash
pip install ipdb
```

```python
import ipdb

def buggy_function(x, y):
    result = x + y
    ipdb.set_trace()  # Colorized, tab completion
    return result * 2
```

**Commands**:
```
(ipdb) p x              # Print x
(ipdb) pp x             # Pretty-print x
(ipdb) l                # List code around current line
(ipdb) w                # Where (stack trace)
(ipdb) u                # Up stack frame
(ipdb) d                # Down stack frame
(ipdb) h                # Help
```

---

### Post-Mortem Debugging

**Debug after exception**:

```python
import pdb
import sys

def buggy_function():
    x = 1
    y = 0
    return x / y  # ZeroDivisionError

try:
    buggy_function()
except:
    pdb.post_mortem(sys.exc_info()[2])
    # Debugger starts at exception point
```

**Automatic on uncaught exception**:
```python
import sys
import pdb

def exception_handler(exc_type, exc_value, exc_traceback):
    if exc_type is KeyboardInterrupt:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    print("Uncaught exception, starting debugger:")
    pdb.post_mortem(exc_traceback)

sys.excepthook = exception_handler

# Now any uncaught exception starts debugger
```

---

## Profiling

### CPU Profiling (cProfile)

**Find slow functions**:

```python
import cProfile
import pstats

def slow_function():
    # Your code here
    pass

# Profile
profiler = cProfile.Profile()
profiler.enable()
slow_function()
profiler.disable()

# Print stats
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 slowest functions
```

**Output**:
```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       10    0.500    0.050    0.800    0.080 mymodule.py:10(slow_function)
      100    0.300    0.003    0.300    0.003 mymodule.py:20(helper)
```

**Sort options**:
- `cumulative` - Total time (includes subfunctions)
- `time` - Internal time (excludes subfunctions)
- `calls` - Number of calls

---

### Profile Decorator

**Profile specific functions**:

```python
import cProfile
import pstats
from functools import wraps

def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(10)

        return result
    return wrapper

@profile
def slow_function():
    # Your code
    pass
```

---

### Line Profiler (line_profiler)

**Profile line-by-line**:

```bash
pip install line_profiler
```

```python
from line_profiler import LineProfiler

def slow_function():
    total = 0
    for i in range(1000000):
        total += i
    return total

profiler = LineProfiler()
profiler.add_function(slow_function)
profiler.enable()
slow_function()
profiler.disable()
profiler.print_stats()
```

**Output**:
```
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
     2                                           def slow_function():
     3         1          2.0      2.0      0.0      total = 0
     4   1000001     150000.0      0.1     30.0      for i in range(1000000):
     5   1000000     350000.0      0.4     70.0          total += i
     6         1          1.0      1.0      0.0      return total
```

---

### Memory Profiling (memory_profiler)

**Find memory leaks**:

```bash
pip install memory_profiler
```

```python
from memory_profiler import profile

@profile
def memory_hog():
    big_list = [0] * (10 ** 7)  # 10M items
    return sum(big_list)

memory_hog()
```

**Output**:
```
Line #    Mem usage    Increment  Occurrences   Line Contents
=============================================================
     2     40.0 MiB     40.0 MiB           1   @profile
     3                                         def memory_hog():
     4    116.4 MiB     76.4 MiB           1       big_list = [0] * (10 ** 7)
     5    116.4 MiB      0.0 MiB           1       return sum(big_list)
```

---

### Sampling Profiler (py-spy)

**Profile running processes (no code changes needed)**:

```bash
pip install py-spy

# Profile running Python process
py-spy top --pid 12345

# Generate flamegraph
py-spy record -o profile.svg --pid 12345
```

**Advantages**:
- ✅ No code modification
- ✅ Profile production code
- ✅ Low overhead
- ✅ Visualizations (flamegraphs)

---

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

## Simple Metrics

### Counter

```python
class Metrics:
    def __init__(self):
        self.counters = {}

    def increment(self, name, value=1):
        self.counters[name] = self.counters.get(name, 0) + value

    def get(self, name):
        return self.counters.get(name, 0)

    def reset(self):
        self.counters = {}

# Usage
metrics = Metrics()

def process_item(item):
    metrics.increment("items_processed")
    if item.is_valid():
        metrics.increment("items_valid")
    else:
        metrics.increment("items_invalid")

# Later
print(f"Processed: {metrics.get('items_processed')}")
print(f"Valid: {metrics.get('items_valid')}")
print(f"Invalid: {metrics.get('items_invalid')}")
```

---

### Histogram

**Track value distributions**:

```python
from collections import defaultdict

class Histogram:
    def __init__(self):
        self.buckets = defaultdict(int)

    def record(self, value):
        # Bucket by value range
        if value < 1:
            bucket = "< 1s"
        elif value < 5:
            bucket = "1-5s"
        elif value < 10:
            bucket = "5-10s"
        else:
            bucket = "> 10s"

        self.buckets[bucket] += 1

    def report(self):
        for bucket, count in sorted(self.buckets.items()):
            print(f"{bucket}: {count}")

# Usage
histogram = Histogram()

for duration in query_durations:
    histogram.record(duration)

histogram.report()
# Output:
# < 1s: 850
# 1-5s: 120
# 5-10s: 25
# > 10s: 5
```

---

## Debugging Best Practices

### 1. Binary Search Debugging

**Narrow down the problem**:

```python
# Problem: Something breaks between start and end

def debug_binary_search():
    # Step 1: Check middle
    middle_result = process_half()
    print(f"Middle result: {middle_result}")

    # Step 2: Narrow to first or second half
    if middle_result == expected:
        # Problem in second half
        debug_second_half()
    else:
        # Problem in first half
        debug_first_half()
```

---

### 2. Rubber Duck Debugging

**Explain code out loud (or to a rubber duck)**:

1. Describe what code *should* do
2. Explain what code *actually* does
3. Often you'll spot the bug while explaining!

---

### 3. Add Assertions

**Catch bugs early**:

```python
def divide(a, b):
    assert b != 0, "Divisor cannot be zero"
    assert isinstance(a, (int, float)), "a must be numeric"
    assert isinstance(b, (int, float)), "b must be numeric"

    result = a / b

    assert isinstance(result, (int, float)), "Result should be numeric"
    return result
```

---

### 4. Simplify and Isolate

**Reduce problem to minimal case**:

```python
# ❌ BAD: Complex function with bug
def complex_function(data, config, options, flags):
    # 100 lines of code
    pass

# ✅ GOOD: Extract minimal failing case
def minimal_failing_case():
    data = [1, 2, 3]
    result = transform(data)  # Fails here
    return result
```

---

## Logging Anti-Patterns

**❌ DON'T**:

```python
# 1. Log sensitive data
logger.info(f"Password: {password}")

# 2. Log in tight loops
for item in million_items:
    logger.info(f"Processing {item}")

# 3. Catch and ignore silently
try:
    critical_operation()
except:
    pass  # Silent failure!

# 4. Over-log (log everything)
logger.debug("Starting function")
logger.debug("Variable x = 1")
logger.debug("Variable y = 2")
logger.debug("Calling helper")
logger.debug("Helper returned")

# 5. Use wrong log level
logger.error("User logged in")  # Should be INFO
logger.info("Database crashed")  # Should be CRITICAL
```

---

## Quick Reference

### Logging
```python
logger.debug("Detailed trace")
logger.info("Normal event")
logger.warning("Unexpected")
logger.error("Error occurred", exc_info=True)
logger.critical("System failure")
```

### Debugging
```python
breakpoint()              # Start debugger
pdb.set_trace()          # Start debugger (old way)
traceback.print_exc()    # Print stack trace
```

### Profiling
```python
# CPU
python -m cProfile -s cumulative script.py

# Memory
@profile  # from memory_profiler
def func(): pass

# Live process
py-spy top --pid 12345
```

### Timing
```python
@timer
def func(): pass

with timer("operation"):
    do_work()
```

---

## Key Takeaways

1. **Structured logging** - Use JSON for machine-readable logs
2. **Appropriate log levels** - DEBUG/INFO/WARNING/ERROR/CRITICAL
3. **Don't log secrets** - Never log passwords, API keys, etc.
4. **Use debugger** - breakpoint() or ipdb for interactive debugging
5. **Profile first** - Don't optimize without profiling
6. **cProfile for CPU** - Find slow functions
7. **memory_profiler for memory** - Find memory leaks
8. **Stack traces on errors** - Always log exc_info=True
9. **Time critical paths** - Use @timer decorator
10. **Simple metrics** - Track counters and histograms

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: python-standards (best practices), testing-guide (test debugging), security-patterns (safe logging)
