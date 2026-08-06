---
name: python-standards
description: "Enforces PEP 8 compliance, applies Black formatting, validates type hints, generates Google-style docstrings, and implements error handling patterns. Use when writing or reviewing Python code. TRIGGER when: python, formatting, type hints, docstrings, PEP 8, black, isort. DO NOT TRIGGER when: non-Python files, markdown, config, shell scripts."
allowed-tools: "Read"
---

# Python Standards Skill

Python code quality standards for autonomous-dev project.

## Code Style (PEP 8 + Black)

| Setting | Value |
|---------|-------|
| Line length | 100 characters |
| Indentation | 4 spaces (no tabs) |
| Quotes | Double quotes |
| Imports | Sorted with isort |

## Type Hints (Required)

All public functions must have type hints on parameters and return:

```python
def process_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    max_lines: int = 1000
) -> Dict[str, any]:
    """Process and return file contents."""
    pass
```

## Docstrings (Google Style)

All public functions/classes need docstrings with Args, Returns, Raises:

```python
def process_data(data: List[Dict], *, batch_size: int = 32) -> ProcessResult:
    """Process data with validation.

    Args:
        data: Input data as list of dicts
        batch_size: Items per batch (default: 32)

    Returns:
        ProcessResult with items and metrics

    Raises:
        ValueError: If data is empty
    """
```

## Error Handling

Every error message must include context, expected state, and docs link:

```python
raise FileNotFoundError(
    f"Config file not found: {path}\n"
    f"Expected: YAML with keys: model, data\n"
    f"See: docs/guides/configuration.md"
)
```

### Exception Hierarchy

```python
class AppError(Exception):
    """Base exception for the application."""
    pass

class ConfigError(AppError):
    """Configuration loading or validation error."""
    pass

class ValidationError(AppError):
    """Input or data validation error."""
    pass

class ExternalServiceError(AppError):
    """Error communicating with external service."""
    pass
```

Use built-in exceptions (`ValueError`, `TypeError`, `FileNotFoundError`) for standard programming errors. Use custom exceptions when callers need to catch specific application-level failures.

### Graceful Degradation

When a non-critical operation fails, log and continue:

```python
try:
    optional_result = enhance_with_cache(data)
except CacheError:
    logging.warning("Cache unavailable, proceeding without cache")
    optional_result = None
```

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ModelTrainer` |
| Functions | snake_case | `train_model()` |
| Constants | UPPER_SNAKE | `MAX_LENGTH` |
| Private | _underscore | `_helper()` |

## Best Practices

1. **Keyword-only args** — use `*` separator for functions with 2+ optional params
2. **Pathlib** — use `Path` not string paths
3. **Context managers** — use `with` for resources
4. **Dataclasses** — for configuration objects

## Quality Check Workflow

Run in this order before committing:

```bash
# 1. Format
black --line-length=100 src/ tests/
# 2. Sort imports
isort --profile=black --line-length=100 src/ tests/
# 3. Lint
flake8 src/ --max-line-length=100
# 4. Type check
mypy src/[project_name]/
# 5. Test with coverage
pytest --cov=src --cov-fail-under=80
```

## Cross-References

- [testing-guide](../testing-guide/SKILL.md) — Testing patterns and TDD methodology
- [error-handling](../error-handling/SKILL.md) — Error handling best practices

## Hard Rules

**FORBIDDEN**:
- Public functions without type hints on parameters and return values
- Bare `except:` or `except Exception:` without re-raising or specific handling
- Mutable default arguments (`def f(items=[])`)
- Using `os.path` when `pathlib.Path` is available

**REQUIRED**:
- All public APIs MUST have Google-style docstrings with Args/Returns/Raises
- All code MUST pass black formatting (100 char line length)
- Imports MUST be sorted with isort (profile=black)
- Keyword-only arguments MUST be used for functions with 2+ optional parameters
