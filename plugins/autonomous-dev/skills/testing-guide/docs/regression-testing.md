# Regression Testing

## Regression Testing

### Purpose
Ensure fixed bugs never return.

### When to Create

- After fixing any bug
- Issue closed with "Closes #123"
- Commit contains "fix:"

### Regression Test Template

```python
# tests/regression/test_regression_suite.py

class TestMLXPatterns:
    """[FRAMEWORK]-specific regression tests."""

    def test_bug_47_mlx_nested_layers(self):
        \"\"\"
        Regression test: [FRAMEWORK] model.layers AttributeError

        Bug: Code tried model.layers[i] (doesn't exist)
        Fix: Use model.model.layers[i] (nested structure)
        Date fixed: 2025-10-18
        Issue: #47

        Ensures bug never returns.
        \"\"\"

        # Arrange
        model = create_mock_mlx_model()

        # Act & Assert: Correct way works
        layer = model.model.layers[0]
        assert layer is not None

        # Assert: Wrong way fails (bug would use this)
        with pytest.raises(AttributeError):
            _ = model.layers
```

### Test Organization

```python
# tests/regression/test_regression_suite.py

class TestMLXPatterns:
    """[FRAMEWORK]-specific bugs."""
    pass

class TestDataProcessing:
    """Data handling bugs."""
    pass

class TestAPIIntegration:
    """External API bugs."""
    pass

class TestErrorHandling:
    """Error handling bugs."""
    pass
```

---
