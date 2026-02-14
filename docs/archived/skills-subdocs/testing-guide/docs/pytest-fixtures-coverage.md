# Pytest Fixtures Coverage

## Pytest Fixtures

### Common Fixtures

```python
# conftest.py

import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_data():
    """Sample training data."""
    return {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    }

@pytest.fixture
def mock_model():
    """Mock [FRAMEWORK] model."""
    class MockModel:
        def __init__(self):
            self.model = type('obj', (object,), {'layers': []})()
    return MockModel()
```

---

## Coverage Targets

### By Test Type

| Test Type | Target Coverage |
|-----------|-----------------|
| Unit | 90%+ |
| Integration | 70%+ |
| Progression | N/A (metric tracking) |
| Regression | N/A (bug prevention) |

### Overall Project

- **Minimum**: 80% (enforced in CI/CD)
- **Target**: 90%
- **Stretch**: 95%

### Check Coverage

```bash
# Run tests with coverage
pytest --cov=src/[project_name] --cov-report=html tests/

# Open coverage report
open htmlcov/index.html

# Show missing lines
pytest --cov=src/[project_name] --cov-report=term-missing tests/
```

---
