# Test Organization Best Practices

## Test Organization

### Directory Structure

```
tests/
├── unit/                    # TDD unit tests
│   ├── test_trainer.py
│   ├── test_lora.py
│   └── test_dpo.py
├── integration/             # TDD integration tests
│   └── test_training_pipeline.py
├── progression/             # Baseline tracking
│   ├── test_lora_accuracy.py
│   ├── test_training_speed.py
│   └── baselines/
│       └── *.json
└── regression/              # Bug prevention
    ├── test_regression_suite.py
    └── README.md
```

### Naming Conventions

**Test Files**: `test_{module}.py`
**Test Functions**: `test_{what_is_being_tested}()`
**Test Classes**: `Test{Feature}`

**Examples**:
- `test_trainer.py` - Tests for trainer module
- `test_train_lora_with_valid_params()` - Specific test
- `TestProgressionLoRAAccuracy` - Progression test class

---

## Best Practices

### ✅ DO

1. **Write tests first** (TDD)
2. **Test one thing per test** (focused)
3. **Use descriptive names** (`test_train_lora_raises_error_on_invalid_model`)
4. **Arrange-Act-Assert** pattern
5. **Mock external dependencies** (APIs, files)
6. **Test edge cases** (empty data, None, negative numbers)
7. **Keep tests fast** (<1 second each)
8. **Maintain 80%+ coverage**

### ❌ DON'T

1. **Don't test implementation details** (test behavior, not internal code)
2. **Don't have test dependencies** (tests should be isolated)
3. **Don't hardcode paths** (use fixtures, temporary directories)
4. **Don't skip tests** (fix them or delete them)
5. **Don't write tests after implementation** (that's not TDD!)
6. **Don't test third-party libraries** (trust they're tested)
7. **Don't ignore failing tests** (fix immediately)

---
