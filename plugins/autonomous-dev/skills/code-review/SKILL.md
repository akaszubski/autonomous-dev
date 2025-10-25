---
name: code-review
type: knowledge
description: This skill should be used when reviewing code or preparing code for review. It provides guidelines for what to look for in reviews, how to write constructive feedback, and standards for review comments.
keywords: code review, review, pr review, pull request review, feedback, comment, critique, quality check
auto_activate: true
---

# Code Review Skill

Code review standards and best practices for providing constructive feedback.

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

### Be Constructive

**Focus on the code, not the person**:

```markdown
# ❌ BAD: Attacks the person
You don't know how to write good code.

# ✅ GOOD: Focuses on the code
This approach doesn't handle edge cases. Consider adding validation.
```

**Provide specific suggestions**:

```markdown
# ❌ BAD: Vague critique
This is wrong.

# ✅ GOOD: Specific suggestion with example
Consider using a set here instead of a list for O(1) lookups.
Currently this is O(n) on each iteration:

```python
if item in items:  # O(n) with list
    ...
```

Suggested change:
```python
items_set = set(items)  # O(n) once
if item in items_set:    # O(1) each time
    ...
```
```

### Provide Context

**Explain WHY the change is needed**:

```markdown
# ❌ BAD: No context
Fix this.

# ✅ GOOD: Explains the problem
This will fail if the file doesn't exist. Consider adding:

```python
if not path.exists():
    raise FileNotFoundError(f"Training data not found: {path}")
```

This prevents cryptic errors later in the pipeline.
```

### Distinguish Severity

Use labels to indicate importance:

```markdown
**nit**: Consider renaming `x` to `model_id` for clarity

**suggestion**: This could be simplified using a dictionary lookup

**issue**: This will cause a memory leak - the cache is never cleared

**blocker**: This breaks backwards compatibility - needs migration path
```

**Severity levels**:
- **nit**: Minor style/readability improvement (non-blocking)
- **suggestion**: Better approach exists (non-blocking)
- **issue**: Bug or problem that should be fixed (blocking)
- **blocker**: Critical issue that must be resolved (blocking)

### Ask Questions

When unsure, ask instead of asserting:

```markdown
# ❌ BAD: Assertive without understanding
This is inefficient and needs to be rewritten.

# ✅ GOOD: Asks first
Is there a reason we're loading the entire file into memory?
For large files, could we process it in chunks instead?
```

### Recognize Good Work

```markdown
✅ Nice use of the strategy pattern here - makes it easy to add new methods.

✅ Great test coverage! The edge cases are well-handled.

✅ Clear naming throughout this module.
```

---

## Review Comment Templates

### Suggesting Improvements

```markdown
**suggestion**: Consider extracting this logic to a separate function for reusability.

Current:
```python
# Repeated logic in multiple places
if user.is_active and user.email_verified and not user.is_banned:
    ...
```

Suggested:
```python
def can_user_access_feature(user):
    return user.is_active and user.email_verified and not user.is_banned

if can_user_access_feature(user):
    ...
```
```

### Identifying Bugs

```markdown
**issue**: This will raise a `KeyError` if the key doesn't exist.

Suggested fix:
```python
# Instead of:
value = config['api_key']

# Use:
value = config.get('api_key')
if value is None:
    raise ValueError("Missing required config: api_key")
```
```

### Performance Concerns

```markdown
**issue**: This query runs inside a loop, causing N+1 queries.

Current approach makes `len(users)` database queries:
```python
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)
```

Suggested batch query:
```python
user_ids = [u.id for u in users]
all_orders = db.query("SELECT * FROM orders WHERE user_id IN (?)", user_ids)
orders_by_user = group_by(all_orders, 'user_id')
```
```

### Test Coverage

```markdown
**suggestion**: Add test for the error case.

Suggested test:
```python
def test_process_data_raises_error_on_empty_input():
    with pytest.raises(ValueError, match="Input cannot be empty"):
        process_data([])
```
```

---

## Responding to Review Feedback

### As the Author (Receiving Feedback)

**1. Read all comments before responding**
- Get full picture before reacting
- Understand reviewer's perspective
- Identify patterns in feedback

**2. Ask clarifying questions**

```markdown
# Good clarifying question
> "This should handle empty lists as well"

Thanks for catching this! Should it return an empty result or raise an error?
I'm leaning toward raising an error since empty input is likely a bug.
```

**3. Acknowledge and implement**

```markdown
# ✅ Agree and done
> "Use a set for O(1) lookup"

Done! Changed to use a set. Performance improved 10x in my local tests.
```

**4. Explain alternative approaches**

```markdown
# 💭 Alternative proposal
> "This could use a dictionary"

I considered that, but went with a dataclass instead because:
- Provides type hints
- Better IDE support
- Validates types at runtime

Thoughts?
```

**5. Defer to separate PR when appropriate**

```markdown
# ✅ Agree but separate PR
> "We should also add retry logic"

Great idea! I'd prefer to address that in a separate PR since:
- This PR is already large
- Retry logic needs its own tests
- Unrelated to the current bug fix

Created #127 to track it.
```

### As the Reviewer (Getting Responses)

**1. Be patient and collaborative**
- Remember: You're on the same team
- Goal is better code, not winning arguments
- Be willing to learn from the author

**2. Approve when issues are addressed**

```markdown
# ✅ Approval comment
Thanks for addressing the feedback! The refactoring looks much cleaner.
Approving.
```

**3. Escalate blockers clearly**

```markdown
# ⛔ Clear blocker
I can't approve this yet due to the backwards compatibility break.

We need to either:
1. Add a migration path for existing users
2. Defer this change to v2.0.0

Happy to discuss the best approach.
```

---

## Review Checklists

### Before Requesting Review

- [ ] **Tests pass locally**: `pytest tests/`
- [ ] **Code formatted**: `black . && isort .`
- [ ] **Linting passes**: `ruff check .`
- [ ] **Type checking passes**: `mypy src/`
- [ ] **No debugging code**: Remove `print()`, `console.log()`, etc.
- [ ] **Documentation updated**: README, docstrings, CHANGELOG
- [ ] **PR description complete**: Summary, changes, testing
- [ ] **Linked to issue**: "Closes #N" in PR description

### During Review

- [ ] **Correctness**: Solves the stated problem
- [ ] **Edge cases**: Handles boundaries, errors, nulls
- [ ] **Design**: SOLID principles, appropriate patterns
- [ ] **Testing**: Unit + integration tests, ≥80% coverage
- [ ] **Readability**: Clear naming, self-documenting
- [ ] **Performance**: No obvious inefficiencies
- [ ] **Security**: Input validation, no secrets committed
- [ ] **Documentation**: Updated docs match code changes

### After Approval

- [ ] **CI passes**: All checks green
- [ ] **Conflicts resolved**: Up to date with main branch
- [ ] **Squash commits**: Clean history (if using squash merge)
- [ ] **Delete branch**: After merge completes

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] code review standards:

- **Required reviews**: All PRs require ≥1 approval
- **CI must pass**: Tests, formatters, linters must be green
- **Coverage**: ≥80% test coverage enforced
- **Review SLA**: Reviewers respond within 24 hours
- **Comment severity**: Use nit/suggestion/issue/blocker labels
- **Merge strategy**: Squash and merge (clean history)

---

## Additional Resources

**Tools**:
- GitHub PR reviews
- GitLab merge requests
- Code review automation (e.g., Reviewable, Danger)

**Books**:
- "Code Complete" by Steve McConnell
- "The Art of Readable Code" by Boswell & Foucher
- "Clean Code" by Robert Martin

**Articles**:
- [Google's Code Review Guidelines](https://google.github.io/eng-practices/review/)
- [Microsoft's Code Review Best Practices](https://docs.microsoft.com/en-us/azure/devops/repos/git/review-code)

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: git-workflow, testing-guide, python-standards
