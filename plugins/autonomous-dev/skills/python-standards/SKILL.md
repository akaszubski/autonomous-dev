---
name: python-standards
version: 1.1.0
type: knowledge
description: Python code quality standards (PEP 8, type hints, docstrings). Use when writing Python code.
keywords: python, pep8, type hints, docstrings, black, isort, formatting
auto_activate: true
allowed-tools: [Read]
---

# Python Standards Skill

Python code quality standards for autonomous-dev project.

**See:** [code-examples.md](code-examples.md) for complete code examples
**See:** [templates.md](templates.md) for organization templates

## When This Activates

- Writing Python code
- Code formatting
- Type hints
- Docstrings
- Keywords: "python", "format", "type", "docstring"

---

## Code Style (PEP 8 + Black)

| Setting | Value |
|---------|-------|
| Line length | 100 characters |
| Indentation | 4 spaces (no tabs) |
| Quotes | Double quotes |
| Imports | Sorted with isort |

```bash
black --line-length=100 src/ tests/
isort --profile=black --line-length=100 src/ tests/
```

---

## Type Hints (Required)

**Rule:** All public functions must have type hints on parameters and return.

```python
def process_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    max_lines: int = 1000
) -> Dict[str, any]:
    """Type hints on all parameters and return."""
    pass
```

**See:** [code-examples.md#type-hints](code-examples.md#type-hints) for complete examples

---

## Docstrings (Google Style)

**Rule:** All public functions/classes need docstrings with Args, Returns, Raises.

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

**See:** [code-examples.md#docstrings-google-style](code-examples.md#docstrings-google-style)

---

## Error Handling

**Rule:** Error messages must include context + expected + docs link.

```python
# ✅ GOOD
raise FileNotFoundError(
    f"Config file not found: {path}\n"
    f"Expected: YAML with keys: model, data\n"
    f"See: docs/guides/configuration.md"
)

# ❌ BAD
raise FileNotFoundError("File not found")
```

**See:** [code-examples.md#error-handling](code-examples.md#error-handling)

---

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ModelTrainer` |
| Functions | snake_case | `train_model()` |
| Constants | UPPER_SNAKE | `MAX_LENGTH` |
| Private | _underscore | `_helper()` |

---

## Best Practices

1. **Keyword-only args** - Use `*` for clarity
2. **Pathlib** - Use `Path` not string paths
3. **Context managers** - Use `with` for resources
4. **Dataclasses** - For configuration objects

```python
# Keyword-only args
def train(data: List, *, learning_rate: float = 1e-4):
    pass

# Pathlib
config = Path("config.yaml").read_text()
```

**See:** [code-examples.md#best-practices](code-examples.md#best-practices)

---

## Code Quality Commands

```bash
flake8 src/ --max-line-length=100       # Linting
mypy src/[project_name]/                # Type checking
pytest --cov=src --cov-fail-under=80    # Coverage
```

---

## Key Takeaways

1. **Type hints** - Required on all public functions
2. **Docstrings** - Google style, with Args/Returns/Raises
3. **Black formatting** - 100 char line length
4. **isort imports** - Sorted and organized
5. **Helpful errors** - Context + expected + docs link
6. **Pathlib** - Use Path not string paths
7. **Keyword args** - Use `*` for clarity
8. **Dataclasses** - For configuration objects

---

## Related Files

- [code-examples.md](code-examples.md) - Complete Python code examples
- [templates.md](templates.md) - File organization templates
