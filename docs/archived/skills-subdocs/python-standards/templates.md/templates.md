# Python Standards - Templates

Organization templates and quick reference tables.

---

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ModelTrainer` |
| Functions | snake_case | `train_model()` |
| Variables | snake_case | `training_data` |
| Constants | UPPER_SNAKE | `MAX_SEQUENCE_LENGTH` |
| Private | _underscore | `_internal_helper()` |

---

## File Organization Template

```
src/[project_name]/
├── __init__.py              # Package init
├── core/                    # Core functionality
│   ├── __init__.py
│   ├── trainer.py
│   └── model.py
├── backends/                # Backend implementations
│   ├── __init__.py
│   ├── mlx_backend.py
│   └── pytorch_backend.py
├── cli/                     # CLI tools
│   ├── __init__.py
│   └── main.py
└── utils/                   # Utilities
    ├── __init__.py
    ├── config.py
    └── logging.py
```

---

## Code Quality Commands

```bash
# Formatting
black --line-length=100 src/ tests/
isort --profile=black --line-length=100 src/ tests/

# Linting
flake8 src/ --max-line-length=100

# Type checking
mypy src/[project_name]/

# Coverage
pytest --cov=src/[project_name] --cov-fail-under=80
```

---

## Formatting Standards

| Setting | Value |
|---------|-------|
| Line length | 100 characters |
| Indentation | 4 spaces (no tabs) |
| Quotes | Double quotes preferred |
| Imports | Sorted with isort |

---

## Class Organization Order

1. Class variables
2. `__init__`
3. Public methods
4. Private methods (`_prefix`)
5. Properties (`@property`)

---

## Imports Order (isort)

1. Standard library (`os`, `sys`, `pathlib`)
2. Third-party (`numpy`, `anthropic`)
3. Local (`from project.module import X`)
