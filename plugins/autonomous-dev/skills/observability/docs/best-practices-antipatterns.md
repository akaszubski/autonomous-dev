# Best Practices Antipatterns

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
