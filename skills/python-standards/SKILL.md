---
name: python-standards
type: knowledge
description: Python code quality standards (PEP 8, type hints, docstrings). Use when writing Python code.
keywords: python, pep8, type hints, docstrings, black, isort, formatting
---

# Python Standards Skill

Python code quality standards for [PROJECT_NAME] project.

## When This Activates
- Writing Python code
- Code formatting
- Type hints
- Docstrings
- Keywords: "python", "format", "type", "docstring"

## Code Style (PEP 8 + Black)

### Formatting
- **Line length**: 100 characters (black --line-length=100)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes preferred
- **Imports**: Sorted with isort

### Running Formatters
```bash
# Black
black --line-length=100 src/ tests/

# isort
isort --profile=black --line-length=100 src/ tests/

# Combined (automatic via hooks)
black src/ && isort src/
```

## Type Hints (Required)

### Function Signatures
```python
from pathlib import Path
from typing import Optional, List, Dict, Union, Tuple


def process_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    max_lines: int = 1000,
    validate: bool = True
) -> Dict[str, any]:
    """Process file with type hints on all parameters and return."""
    pass
```

### Generic Types
```python
from typing import List, Dict, Set, Tuple, Optional, Union

# Collections
items: List[str] = ["a", "b", "c"]
mapping: Dict[str, int] = {"a": 1, "b": 2}
unique: Set[int] = {1, 2, 3}
pair: Tuple[str, int] = ("key", 42)

# Optional (can be None)
maybe_value: Optional[str] = None

# Union (multiple types)
flexible: Union[str, int] = "text"
```

### Class Type Hints
```python
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class TrainingConfig:
    """Training configuration with type hints."""

    model_name: str
    learning_rate: float = 1e-4
    batch_size: int = 32
    num_epochs: int = 3
    use_lora: bool = True

    # Class variable
    DEFAULT_LR: ClassVar[float] = 1e-4
```

## Docstrings (Google Style)

### Function Docstrings
```python
def train_model(
    data: List[Dict],
    *,
    learning_rate: float = 1e-4,
    num_epochs: int = 3
) -> TrainResult:
    """Train model on provided data.

    This function implements the training loop using the specified
    hyperparameters. It supports both LoRA and full fine-tuning.

    Args:
        data: Training data as list of dicts with 'input' and 'output' keys
        learning_rate: Learning rate for optimizer (default: 1e-4)
        num_epochs: Number of training epochs (default: 3)

    Returns:
        TrainResult containing loss, metrics, and trained model

    Raises:
        ValueError: If data is empty or invalid format
        TrainingError: If training fails

    Example:
        >>> data = [{"input": "Q", "output": "A"}]
        >>> result = train_model(data, learning_rate=1e-3)
        >>> print(result.final_loss)
        0.245
    """
    pass
```

### Class Docstrings
```python
class ModelTrainer:
    """Training orchestrator for [PROJECT_NAME] models.

    This class handles the complete training workflow including
    data preparation, model initialization, training loop, and
    evaluation.

    Args:
        model_name: HuggingFace model identifier
        config: Training configuration
        device: Device for training ('gpu' or 'cpu')

    Attributes:
        model: Loaded [FRAMEWORK] model
        optimizer: Training optimizer
        metrics: Training metrics tracker

    Example:
        >>> trainer = ModelTrainer("model-name", config)
        >>> result = trainer.train(train_data)
        >>> trainer.save("checkpoint.npz")
    """

    def __init__(
        self,
        model_name: str,
        config: TrainingConfig,
        device: str = "gpu"
    ):
        self.model_name = model_name
        self.config = config
        self.device = device
```

## Error Handling

### Helpful Error Messages
```python
# ✅ GOOD: Context + Expected + Docs
def load_config(path: Path) -> Dict:
    """Load configuration file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Expected YAML file with keys: model, data, training\n"
            f"See example: docs/examples/config.yaml\n"
            f"See guide: docs/guides/configuration.md"
        )

    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML in config file: {path}\n"
            f"Error: {e}\n"
            f"See guide: docs/guides/configuration.md"
        )


# ❌ BAD: Generic error
def load_config(path):
    if not path.exists():
        raise FileNotFoundError("File not found")
```

### Custom Exceptions
```python
class ReAlignError(Exception):
    """Base exception for [PROJECT_NAME]."""
    pass


class ConfigError(ReAlignError):
    """Configuration error."""
    pass


class TrainingError(ReAlignError):
    """Training error."""
    pass


# Usage
def validate_config(config: Dict) -> None:
    """Validate configuration."""
    required = ["model", "data", "training"]
    missing = [k for k in required if k not in config]

    if missing:
        raise ConfigError(
            f"Missing required config keys: {missing}\n"
            f"Required: {required}\n"
            f"See: docs/guides/configuration.md"
        )
```

## Code Organization

### Imports Order (isort)
```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party
import [framework].core as mx
import numpy as np
from anthropic import Anthropic

# 3. Local
from [project_name].core.trainer import Trainer
from [project_name].utils.config import load_config
```

### Function/Class Organization
```python
class Model:
    """Model class."""

    # 1. Class variables
    DEFAULT_LR = 1e-4

    # 2. __init__
    def __init__(self, name: str):
        self.name = name

    # 3. Public methods
    def train(self, data: List) -> None:
        """Public training method."""
        pass

    # 4. Private methods
    def _prepare_data(self, data: List) -> List:
        """Private helper method."""
        pass

    # 5. Properties
    @property
    def num_parameters(self) -> int:
        """Number of trainable parameters."""
        return sum(p.size for p in self.parameters())
```

## Naming Conventions

```python
# Classes: PascalCase
class ModelTrainer:
    pass

# Functions/variables: snake_case
def train_model():
    training_data = []

# Constants: UPPER_SNAKE_CASE
MAX_SEQUENCE_LENGTH = 2048
DEFAULT_LEARNING_RATE = 1e-4

# Private: _leading_underscore
def _internal_helper():
    pass

_internal_cache = {}
```

## Best Practices

### Use Keyword-Only Arguments
```python
# ✅ GOOD: Clear, prevents positional errors
def train(
    data: List,
    *,
    learning_rate: float = 1e-4,
    batch_size: int = 32
):
    pass

# Must use: train(data, learning_rate=1e-3)


# ❌ BAD: Easy to mix up arguments
def train(data, learning_rate=1e-4, batch_size=32):
    pass
```

### Use Pathlib
```python
from pathlib import Path

# ✅ GOOD: Pathlib
config_path = Path("config.yaml")
if config_path.exists():
    content = config_path.read_text()

# ❌ BAD: String paths
import os
if os.path.exists("config.yaml"):
    with open("config.yaml") as f:
        content = f.read()
```

### Use Context Managers
```python
# ✅ GOOD: Automatic cleanup
with open(path) as f:
    data = f.read()

# ✅ GOOD: Custom context manager
from contextlib import contextmanager

@contextmanager
def training_context():
    """Setup/teardown for training."""
    setup_training()
    try:
        yield
    finally:
        cleanup_training()
```

### Use Dataclasses
```python
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    """Configuration with dataclass."""

    model_name: str
    learning_rate: float = 1e-4
    epochs: int = 3
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate after initialization."""
        if self.learning_rate <= 0:
            raise ValueError("Learning rate must be positive")


# Usage
config = Config(model_name="model", tags=["test"])
```

## Code Quality Checks

### Flake8 (Linting)
```bash
flake8 src/ --max-line-length=100
```

### MyPy (Type Checking)
```bash
mypy src/[project_name]/
```

### Coverage
```bash
pytest --cov=src/[project_name] --cov-fail-under=80
```

## File Organization

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

## Anti-Patterns to Avoid

```python
# ❌ BAD: No type hints
def process(data, config):
    pass

# ❌ BAD: No docstring
def train_model(data, lr=1e-4):
    pass

# ❌ BAD: Unclear names
def proc(d, c):
    x = d['k']
    return x

# ❌ BAD: Mutable default argument
def add_item(items=[]):
    items.append("new")
    return items

# ❌ BAD: Generic exception
try:
    process()
except:
    pass
```

## Key Takeaways

1. **Type hints** - Required on all public functions
2. **Docstrings** - Google style, with examples
3. **Black formatting** - 100 char line length
4. **isort imports** - Sorted and organized
5. **Helpful errors** - Context + expected + docs link
6. **Pathlib** - Use Path not string paths
7. **Keyword args** - Use * for clarity
8. **Dataclasses** - For configuration objects
