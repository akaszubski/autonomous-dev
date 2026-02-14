# Code Review - Detailed Guide

## When This Skill Activates

- Reviewing pull requests
- Conducting code reviews
- Writing review comments
- Responding to review feedback
- Keywords: "review", "pr", "feedback", "comment", "critique"

---

## What to Look For in Code Reviews

### 1. Correctness

**Does it solve the stated problem?**

```python
# ❌ BAD: Doesn't handle the edge case mentioned in the issue
def divide(a, b):
    return a / b  # Issue #42 says we need to handle zero division

# ✅ GOOD: Solves the stated problem
def divide(a, b):
    """Divide two numbers with zero-division handling.

    Closes #42
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

**Are there edge cases not handled?**

Common edge cases to check:
- Empty collections (lists, dicts, sets)
- Null/None values
- Boundary values (0, MAX_INT, empty string)
- Concurrent access (race conditions)
- Network failures (timeouts, retries)
- File system issues (permissions, disk full)

**Potential bugs or race conditions?**

```python
# ❌ BAD: Race condition
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Not thread-safe!

# ✅ GOOD: Thread-safe
import threading

class Counter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.count += 1
```

---

### 2. Design Quality

**Follows SOLID principles?**

- **S**ingle Responsibility: One class, one purpose
- **O**pen/Closed: Open for extension, closed for modification
- **L**iskov Substitution: Subtypes must be substitutable
- **I**nterface Segregation: Many specific interfaces > one general
- **D**ependency Inversion: Depend on abstractions, not concretions

**Example - Single Responsibility**:

```python
# ❌ BAD: Class does too much
class UserManager:
    def create_user(self, data): ...
    def send_email(self, user): ...
    def log_activity(self, action): ...
    def calculate_metrics(self): ...

# ✅ GOOD: Each class has one responsibility
class UserRepository:
    def create_user(self, data): ...

class EmailService:
    def send_welcome_email(self, user): ...

class ActivityLogger:
    def log(self, action): ...

class MetricsCalculator:
    def calculate_user_metrics(self): ...
```

**Appropriate abstractions?**

```python
# ❌ BAD: Leaky abstraction
class Database:
    def query(self, sql):  # Exposes SQL details
        return self.connection.execute(sql)

# ✅ GOOD: Clean abstraction
class UserRepository:
    def find_by_email(self, email):  # Hides implementation
        return self._query_users(email=email)
```

**Pattern usage correct?**

Check if patterns are:
- Used appropriately (not over-engineering)
- Implemented correctly
- Solving the right problem

---

### 3. Testing Coverage

**Sufficient test coverage?**

Minimum requirements:
- ✅ **Unit tests**: Test individual functions/methods
- ✅ **Integration tests**: Test component interactions
- ✅ **Edge cases**: Test boundaries and error conditions
- ✅ **Target**: ≥80% code coverage

**Tests cover edge cases?**

```python
# Example: Testing edge cases
def test_divide_by_zero_raises_error():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

def test_divide_positive_numbers():
    assert divide(10, 2) == 5

def test_divide_negative_numbers():
    assert divide(-10, 2) == -5

def test_divide_fractional_result():
    assert divide(5, 2) == 2.5
```

**Tests are deterministic?**

```python
# ❌ BAD: Non-deterministic test (flaky)
def test_process_items():
    items = get_random_items()  # Different every time!
    result = process(items)
    assert len(result) > 0

# ✅ GOOD: Deterministic test
def test_process_items():
    items = [{"id": 1}, {"id": 2}, {"id": 3}]  # Fixed input
    result = process(items)
    assert len(result) == 3
```

---

### 4. Readability

**Clear naming?**

```python
# ❌ BAD: Unclear names
def fn(x, y):
    return x > y

# ✅ GOOD: Clear names
def is_price_above_threshold(price: float, threshold: float) -> bool:
    return price > threshold
```

**Self-documenting code?**

```python
# ❌ BAD: Needs comments to understand
def calc(d):
    if d > 30:
        return d * 0.9  # What does 30 mean? What does 0.9 mean?
    return d

# ✅ GOOD: Self-documenting
BULK_DISCOUNT_THRESHOLD_DAYS = 30
BULK_DISCOUNT_RATE = 0.10

def calculate_rental_price(days_rented: int) -> float:
    """Calculate rental price with bulk discount for 30+ days."""
    if days_rented >= BULK_DISCOUNT_THRESHOLD_DAYS:
        discount_multiplier = 1 - BULK_DISCOUNT_RATE
        return days_rented * discount_multiplier
    return days_rented
```

**Comments where necessary?**

Good comments explain **WHY**, not WHAT:

```python
# ❌ BAD: States the obvious
counter += 1  # Increment counter

# ✅ GOOD: Explains why
# Skip first batch - it's used for model warmup
counter += 1
```

---

### 5. Performance

**Obvious inefficiencies?**

```python
# ❌ BAD: O(n²) when O(n) possible
def find_duplicates(items):
    duplicates = []
    for item in items:
        for other in items:  # Nested loop!
            if item == other:
                duplicates.append(item)
    return duplicates

# ✅ GOOD: O(n) using set
def find_duplicates(items):
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return list(duplicates)
```

**Unnecessary copies or allocations?**

```python
# ❌ BAD: Creates new list each iteration
def process_items(items):
    result = []
    for item in items:
        result = result + [process(item)]  # New list!
    return result

# ✅ GOOD: Modifies in place
def process_items(items):
    result = []
    for item in items:
        result.append(process(item))  # In-place append
    return result
```

**Appropriate data structures?**

| Use Case | Wrong | Right |
|----------|-------|-------|
| Frequent membership checks | List (O(n)) | Set (O(1)) |
| Ordered key-value pairs | Dict (unordered) | OrderedDict or dict (Python 3.7+) |
| FIFO queue | List (O(n) pop) | deque (O(1) pop) |
| Fixed-size numeric array | List | numpy.array |

---

## How to Write Review Comments
