# Debugging

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
