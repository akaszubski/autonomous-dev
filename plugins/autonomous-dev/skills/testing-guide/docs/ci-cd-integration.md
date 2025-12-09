# Ci Cd Integration

## CI/CD Integration

### Pre-Push Hook

```bash
# Run all tests before push
pytest tests/ -v

# Check coverage
pytest --cov=src/[project_name] --cov-report=term --cov-fail-under=80 tests/
```

### GitHub Actions

```yaml
- name: Run Tests
  run: |
    pytest tests/ -v --cov=src/[project_name] --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

---

## Quick Reference

### Test Types Decision Matrix

| Scenario | Test Type | Location |
|----------|-----------|----------|
| New feature | **TDD** | tests/unit/ |
| Optimize performance | **Progression** | tests/progression/ |
| Fixed bug | **Regression** | tests/regression/ |
| Multiple components | **Integration** | tests/integration/ |

### Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/unit/test_trainer.py

# Specific test
pytest tests/unit/test_trainer.py::test_train_lora

# With coverage
pytest --cov=src/[project_name] tests/

# Verbose output
pytest -v tests/

# Stop on first failure
pytest -x tests/

# Parallel execution
pytest -n auto tests/
```

---
