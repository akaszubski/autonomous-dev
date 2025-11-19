# Tests

Unit and integration tests for the autonomous-dev plugin.

## Setup

**Development Environment**: Before running tests, ensure you've completed the
development setup in [DEVELOPMENT.md](../docs/DEVELOPMENT.md), including creating
the `autonomous_dev` symlink.

If you encounter `ModuleNotFoundError`, see [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md).

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/unit/scripts/test_session_tracker.py

# Run tests with markers
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── hooks/              # Tests for hook files
│   │   └── test_auto_format.py
│   └── scripts/            # Tests for scripts
│       └── test_session_tracker.py
└── integration/            # Integration tests (slower, end-to-end)
    └── (future tests)
```

## Test Organization

### Unit Tests
- **Purpose**: Test individual functions/classes in isolation
- **Speed**: Fast (< 1 second per test)
- **Dependencies**: Minimal, use mocks for external calls
- **Coverage Target**: 80%+ for all Python code

### Integration Tests
- **Purpose**: Test complete workflows end-to-end
- **Speed**: Slower (may take several seconds)
- **Dependencies**: May use temporary directories, real commands
- **Examples**: Testing full plugin installation, agent workflows

## Writing Tests

### Unit Test Example

```python
def test_format_python_runs_black():
    """Test that format_python runs black."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        files = [Path("test.py")]
        success, message = format_python(files)

        assert success is True
        assert "black" in message
```

### Test Naming

- Test files: `test_<module>.py`
- Test functions: `test_<what_it_tests>()`
- Test classes: `Test<ClassName>`

### Markers

Use pytest markers to organize tests:

```python
@pytest.mark.unit
def test_simple_function():
    pass

@pytest.mark.integration
@pytest.mark.slow
def test_full_workflow():
    pass
```

## Coverage

Coverage is measured for:
- `plugins/autonomous-dev/hooks/` - Hook implementation files
- `scripts/` - Utility scripts

Coverage reports:
- Terminal: Shows missing lines after test run
- HTML: Open `htmlcov/index.html` in browser
- XML: For CI/CD integration

### Viewing Coverage Report

```bash
# Run tests with coverage
pytest --cov

# Generate HTML report
pytest --cov --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Configuration

Test configuration is in `pytest.ini` at the project root:

- Test discovery paths
- Coverage settings
- Output formatting
- Test markers

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Use Fixtures**: Share common setup with pytest fixtures
3. **Mock External Calls**: Use `unittest.mock` for subprocess, file I/O
4. **Descriptive Names**: Test names should describe what they test
5. **One Assertion Focus**: Each test should verify one specific behavior
6. **Fast Tests**: Unit tests should run in milliseconds

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest --cov --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Import Errors

If you get import errors, ensure:
1. You're running pytest from the project root
2. The project structure matches the expected layout
3. `__init__.py` files exist in test directories

### Mock Issues

If mocks aren't working:
1. Check the patch target path matches the import path
2. Use `patch.object()` for class methods
3. Verify mock is applied before the function runs

### Coverage Gaps

To find untested code:
```bash
pytest --cov --cov-report=term-missing
```

This shows line numbers of code not covered by tests.
