# Profiling

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
