---
name: engineering-standards
type: knowledge
description: General engineering best practices - code quality, git workflows, code review, refactoring
keywords: code quality, git, refactoring, code review, best practices, clean code, naming, comments
auto_activate: true
---

# Engineering Standards Skill

General software engineering best practices and standards.

## When This Activates
- Writing or reviewing code
- Git operations (commits, PRs)
- Refactoring
- Code reviews
- Keywords: "code quality", "refactor", "git", "review", "best practice"

---

## Code Quality Principles

### Clean Code

**Rule**: Code should be self-explanatory

```python
# ❌ BAD: Unclear names, magic numbers
def calc(d):
    if d > 30:
        return d * 0.9
    return d

# ✅ GOOD: Clear names, no magic numbers
BULK_DISCOUNT_THRESHOLD = 30
BULK_DISCOUNT_RATE = 0.10

def calculate_total_price(days_rented: int) -> float:
    """Calculate rental price with bulk discount for 30+ days."""
    if days_rented >= BULK_DISCOUNT_THRESHOLD:
        discount = 1 - BULK_DISCOUNT_RATE
        return days_rented * discount
    return days_rented
```

---

### Naming Conventions

**Variables & Functions**: `snake_case`, descriptive

```python
# ❌ BAD
x = 10
def fn(a, b): ...

# ✅ GOOD
max_retries = 10
def calculate_alignment_score(intent_score: float, pattern_score: float): ...
```

**Classes**: `PascalCase`, noun

```python
# ❌ BAD
class process_data: ...

# ✅ GOOD
class DataProcessor: ...
class ModelTrainer: ...
```

**Constants**: `UPPER_SNAKE_CASE`

```python
# ❌ BAD
default_timeout = 30

# ✅ GOOD
DEFAULT_TIMEOUT_SECONDS = 30
MAX_BATCH_SIZE = 128
```

**Booleans**: Use question format

```python
# ❌ BAD
valid = True
active = False

# ✅ GOOD
is_valid = True
has_errors = False
can_retry = True
should_log = False
```

---

### Comments

**Good Comments**:
- **Why**, not what
- **Warnings** about non-obvious behavior
- **Context** for complex logic

```python
# ❌ BAD: Stating the obvious
# Increment counter by 1
counter += 1

# ✅ GOOD: Explains why
# Skip first batch - it's used for warmup
counter += 1

# ❌ BAD: Redundant
def calculate_total(items):
    """Calculate total."""  # Useless docstring
    ...

# ✅ GOOD: Adds value
def calculate_total(items):
    """Calculate order total including tax and shipping.

    Note: Tax calculation varies by region. Uses simplified
    10% flat tax for MVP. See issue #42 for regional tax support.
    """
    ...
```

**When to Comment**:
- Complex algorithms
- Non-obvious optimizations
- Temporary workarounds (with issue link)
- Regulatory/compliance requirements

**When NOT to Comment**:
- Self-explanatory code
- Repeating function/variable names
- Outdated information (delete instead)

---

### Function Design

**Rule**: Functions should do ONE thing

```python
# ❌ BAD: Does too much
def process_user_data(data):
    # Validate
    if not data.get('email'):
        raise ValueError("Missing email")

    # Transform
    normalized = data['email'].lower().strip()

    # Save to DB
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("INSERT ...")

    # Send email
    smtp = smtplib.SMTP(...)
    smtp.send_message(...)

    # Log
    logging.info("User processed")

# ✅ GOOD: Single responsibility per function
def validate_user_data(data):
    """Validate user data structure and required fields."""
    if not data.get('email'):
        raise ValueError("Missing email")

def normalize_email(email: str) -> str:
    """Normalize email to lowercase and trim whitespace."""
    return email.lower().strip()

def save_user(user_data):
    """Persist user to database."""
    ...

def send_welcome_email(email: str):
    """Send welcome email to new user."""
    ...

def process_user_data(data):
    """Process new user registration."""
    validate_user_data(data)
    normalized_email = normalize_email(data['email'])
    user = save_user({**data, 'email': normalized_email})
    send_welcome_email(user.email)
    logging.info(f"User processed: {user.id}")
```

**Function Length**: Aim for <20 lines. If longer, consider splitting.

---

### Error Handling

**Be Specific**:

```python
# ❌ BAD: Bare except catches everything
try:
    result = risky_operation()
except:
    pass  # Silent failure!

# ✅ GOOD: Catch specific exceptions
try:
    result = risky_operation()
except ValueError as e:
    logging.error(f"Invalid input: {e}")
    raise
except NetworkError as e:
    logging.error(f"Network failure: {e}")
    # Retry or use fallback
    result = fallback_operation()
```

**Informative Error Messages**:

```python
# ❌ BAD: Vague error
raise ValueError("Invalid input")

# ✅ GOOD: Specific, actionable error
raise ValueError(
    f"Model ID '{model_id}' not found.\n"
    f"Expected format: 'org/model-name' (e.g., '[model_repo]/Llama-3.2-3B').\n"
    f"See: https://huggingface.co/[model_repo] for available models."
)
```

---

## Git Workflow

### Commit Messages

**Format**: `<type>: <description>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding/updating tests
- `chore`: Tooling, dependencies, config

```bash
# ❌ BAD
git commit -m "updates"
git commit -m "fixed stuff"
git commit -m "wip"

# ✅ GOOD
git commit -m "feat: add PDF/EPUB content extraction"
git commit -m "fix: correct nested layer access in [FRAMEWORK] models"
git commit -m "docs: update QUICKSTART with new training methods"
git commit -m "refactor: extract validation logic to separate module"
git commit -m "test: add integration tests for data curator"
```

**Commit Body** (for complex changes):

```bash
git commit -m "feat: implement DPO training method

- Add DPOStrategy class with preference pair handling
- Integrate with existing Trainer interface
- Update docs with DPO examples

Closes #15"
```

---

### Branch Naming

**Format**: `<type>/<short-description>`

```bash
# ❌ BAD
git checkout -b new-feature
git checkout -b fix
git checkout -b john-branch

# ✅ GOOD
git checkout -b feat/pdf-epub-support
git checkout -b fix/[framework]-layer-access
git checkout -b refactor/data-curator-validation
git checkout -b docs/update-training-guide
```

---

### Pull Request Guidelines

**Title**: Same as commit message format

**Description Template**:

```markdown
## Summary
Brief description of changes (1-3 sentences)

## Changes
- Bulleted list of key changes
- Each bullet should be atomic

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No new warnings

Closes #<issue-number>
```

---

## Code Review Standards

### What to Look For

**Correctness**:
- Does it solve the stated problem?
- Are there edge cases not handled?
- Potential bugs or race conditions?

**Design**:
- Follows SOLID principles?
- Appropriate abstractions?
- Pattern usage correct?

**Testing**:
- Sufficient test coverage?
- Tests cover edge cases?
- Tests are deterministic?

**Readability**:
- Clear naming?
- Self-documenting code?
- Comments where necessary?

**Performance**:
- Obvious inefficiencies?
- Unnecessary copies or allocations?
- Appropriate data structures?

---

### Review Comments

**Be Constructive**:

```markdown
# ❌ BAD
This is wrong.

# ✅ GOOD
Consider using a set here instead of a list for O(1) lookups.
Currently this is O(n) on each iteration.
```

**Provide Context**:

```markdown
# ❌ BAD
Fix this.

# ✅ GOOD
This will fail if the file doesn't exist. Consider adding:
```python
if not path.exists():
    raise FileNotFoundError(f"Training data not found: {path}")
```
```

**Distinguish Severity**:

```markdown
**nit**: Consider renaming `x` to `model_id` for clarity

**suggestion**: This could be simplified using a dictionary lookup

**issue**: This will cause a memory leak - the cache is never cleared

**blocker**: This breaks backwards compatibility - needs migration path
```

---

## Refactoring Best Practices

### When to Refactor

**Good Reasons**:
- Code violates SOLID principles
- Duplicated logic (DRY violation)
- Hard to test or modify
- Performance bottleneck (measured, not assumed)

**Bad Reasons**:
- "Looks ugly" (subjective)
- Different from your preferred style
- Not using latest language features
- Premature optimization

---

### Refactoring Process

**1. Ensure Tests Exist**:
```bash
# Before refactoring, verify tests pass
pytest tests/

# Add tests if missing
```

**2. Make Small, Incremental Changes**:
```bash
# ❌ BAD: Refactor everything at once
git commit -m "refactor: complete rewrite of trainer module"

# ✅ GOOD: Incremental steps
git commit -m "refactor: extract validation logic to validator module"
git commit -m "refactor: replace dict with dataclass for config"
git commit -m "refactor: simplify error handling in trainer"
```

**3. Run Tests After Each Change**:
```bash
pytest tests/ && git add . && git commit
```

**4. Keep Behavior Identical**:
- Refactoring should NOT change behavior
- Tests should pass before and after
- If behavior changes, it's a feature/fix, not refactoring

---

### Common Refactoring Techniques

**Extract Function**:
```python
# Before
def process_order(order):
    total = 0
    for item in order.items:
        price = item.base_price
        if item.quantity > 10:
            price *= 0.9
        total += price * item.quantity

# After
def calculate_item_price(item):
    price = item.base_price
    if item.quantity > 10:
        price *= BULK_DISCOUNT_RATE
    return price * item.quantity

def process_order(order):
    return sum(calculate_item_price(item) for item in order.items)
```

**Replace Magic Numbers**:
```python
# Before
if age > 18:
    ...

# After
LEGAL_ADULT_AGE = 18
if age > LEGAL_ADULT_AGE:
    ...
```

**Introduce Parameter Object**:
```python
# Before
def create_user(name, email, age, address, phone):
    ...

# After
@dataclass
class UserData:
    name: str
    email: str
    age: int
    address: str
    phone: str

def create_user(user_data: UserData):
    ...
```

---

## Performance Best Practices

### Measure First

```python
import time

# ❌ BAD: Optimize without measuring
# "This feels slow, let me rewrite it"

# ✅ GOOD: Measure, then optimize
start = time.time()
result = potentially_slow_function()
elapsed = time.time() - start
logging.info(f"Function took {elapsed:.2f}s")

# Or use profiler
import cProfile
cProfile.run('my_function()')
```

---

### Common Optimizations

**Use Appropriate Data Structures**:

```python
# ❌ BAD: O(n) lookup
items = ['a', 'b', 'c', ...]
if 'x' in items:  # O(n)
    ...

# ✅ GOOD: O(1) lookup
items = {'a', 'b', 'c', ...}
if 'x' in items:  # O(1)
    ...
```

**Avoid Repeated Computation**:

```python
# ❌ BAD: Recomputes len() each iteration
for i in range(len(items)):
    if i < len(items) - 1:  # len() called n times!
        ...

# ✅ GOOD: Compute once
n = len(items)
for i in range(n):
    if i < n - 1:
        ...
```

**Lazy Evaluation**:

```python
# ❌ BAD: Generates entire list in memory
results = [expensive_function(x) for x in huge_list]
first_5 = results[:5]

# ✅ GOOD: Generator (lazy evaluation)
results = (expensive_function(x) for x in huge_list)
first_5 = list(itertools.islice(results, 5))
```

---

## Dependency Management

### Version Pinning

**In `requirements.txt`**:
```
# ❌ BAD: Unpinned (breaks reproducibility)
[framework]
torch

# ✅ GOOD: Pinned versions
[framework]==0.19.3
torch==2.1.0
```

**For Libraries (setup.py/pyproject.toml)**:
```python
# ❌ BAD: Too strict (prevents security updates)
install_requires=['[framework]==0.19.3']

# ✅ GOOD: Compatible range
install_requires=['[framework]>=0.19.0,<0.20.0']
```

---

### Virtual Environments

**Always Use Virtual Environments**:

```bash
# ❌ BAD: Install globally
pip install [framework]

# ✅ GOOD: Use venv
python -m venv venv
source venv/bin/activate
pip install [framework]
```

---

## Documentation Standards

### README Structure

```markdown
# Project Name

Brief description (1-2 sentences)

## Features
- Key feature 1
- Key feature 2

## Installation
```bash
pip install package-name
```

## Quick Start
```python
# Minimal working example
```

## Documentation
- [Full docs](link)
- [API reference](link)

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## License
MIT
```

---

### Code Documentation

**Module Docstrings**:
```python
"""Data curator module for extracting training data.

This module provides tools for extracting data from multiple
sources (web, PDFs, EPUBs) and preparing it for model training.

Usage:
    from [project_name].curator import DataCurator
    curator = DataCurator()
    data = curator.extract_from_pdf("document.pdf")
"""
```

**Function Docstrings** (Google style):
```python
def train_model(
    model_id: str,
    dataset_path: Path,
    method: str = "lora",
    *,
    epochs: int = 3,
    learning_rate: float = 1e-4
) -> TrainingResult:
    """Train a model using specified method.

    Args:
        model_id: HuggingFace model ID (e.g., '[model_repo]/Llama-3.2-3B')
        dataset_path: Path to training dataset (JSON or CSV)
        method: Training method - 'lora', 'dpo', or 'full'
        epochs: Number of training epochs (default: 3)
        learning_rate: Learning rate for optimizer (default: 1e-4)

    Returns:
        TrainingResult with metrics and model path

    Raises:
        ValueError: If model_id not found or dataset invalid
        FileNotFoundError: If dataset_path doesn't exist

    Example:
        >>> result = train_model(
        ...     "[model_repo]/Llama-3.2-3B-Instruct-4bit",
        ...     Path("data/train.json"),
        ...     method="lora",
        ...     epochs=5
        ... )
        >>> print(f"Final loss: {result.final_loss}")
    """
    ...
```

---

## Testing Standards

**(See testing-guide skill for comprehensive methodology)**

**Key Principles**:
- Write tests FIRST (TDD)
- One assert per test (mostly)
- Test behavior, not implementation
- Descriptive test names

```python
# ❌ BAD
def test_1():
    assert func() == 5

# ✅ GOOD
def test_calculate_total_applies_bulk_discount_for_30_plus_days():
    days = 35
    expected = 35 * 0.90  # 10% discount
    actual = calculate_total_price(days)
    assert actual == expected
```

---

## Continuous Integration

**Minimum CI Checks**:
1. Tests pass (`pytest`)
2. Code formatted (`black --check`, `isort --check`)
3. Type checking (`mypy`)
4. Linting (`ruff` or `pylint`)
5. Coverage ≥80% (`pytest --cov`)

**GitHub Actions Example**:
```yaml
- name: Run tests
  run: pytest tests/ --cov=src/ --cov-report=term-missing

- name: Check coverage
  run: |
    COVERAGE=$(pytest --cov=src/ --cov-report=json | jq .totals.percent_covered)
    if (( $(echo "$COVERAGE < 80" | bc -l) )); then
      echo "Coverage $COVERAGE% below 80% threshold"
      exit 1
    fi
```

---

## Security Standards

**(See security-patterns skill for comprehensive guide)**

**Key Principles**:
- Never commit secrets (use `.env`)
- Validate all user input
- Use parameterized queries (SQL injection prevention)
- Keep dependencies updated
- Principle of least privilege

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] follows these standards:

- **Git**: Conventional commits (`feat:`, `fix:`, etc.)
- **Code Quality**: Black + isort formatting, type hints required
- **Testing**: TDD workflow, ≥80% coverage
- **Documentation**: Google-style docstrings, comprehensive guides
- **CI/CD**: Automated testing, coverage checks, security scans

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: python-standards, architecture-patterns, testing-guide, security-patterns
