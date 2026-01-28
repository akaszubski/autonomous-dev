# Performance Optimization Tests - Phase 8+ (TDD Red Phase)

## Overview

This directory contains **96 failing TDD tests** for GitHub Issue #46 Phases 8.5-11 performance optimization. All tests are written FIRST (red phase) before implementation.

**Status**: FAILING (expected - no implementation yet)
**Framework**: pytest with fixtures, mocking, and AAA pattern
**Coverage**: 4 phases, 23 test classes, 96 individual tests

---

## Quick Start

### Run All Tests
```bash
cd ${PROJECT_ROOT}
source .venv/bin/activate
python -m pytest tests/unit/performance/ -v
```

### Run Specific Phase
```bash
# Phase 8.5: Profiler Integration
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py -v

# Phase 9: Model Downgrade
python -m pytest tests/unit/performance/test_phase9_model_downgrade.py -v

# Phase 10: Prompt Streamlining
python -m pytest tests/unit/performance/test_phase10_prompt_streamlining.py -v

# Phase 11: Partial Parallelization
python -m pytest tests/unit/performance/test_phase11_partial_parallelization.py -v
```

### Run Single Test Class
```bash
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py::TestPerformanceTimerWrapping -v
```

### Run with Verbose Output
```bash
python -m pytest tests/unit/performance/test_phase8_5_profiler_integration.py::TestPerformanceTimerWrapping::test_performance_timer_measures_execution_duration -vvs
```

---

## Test Files

### Phase 8.5: Profiler Integration (27 tests)
**File**: `test_phase8_5_profiler_integration.py`

Tests for PerformanceTimer context manager, performance log aggregation, bottleneck detection, and path security validation.

**Key Test Classes**:
- `TestPerformanceTimerWrapping` - Timer accuracy and attributes (5 tests)
- `TestAnalyzePerformanceLogsAggregation` - Metrics calculation (7 tests)
- `TestAnalyzePerformanceLogsBottleneckDetection` - Top 3 slowest agents (3 tests)
- `TestPerformanceLogJsonFormat` - JSON structure validation (6 tests)
- `TestPerformanceLogPathValidation` - CWE-22 security (6 tests)
- `TestPerformanceTimerIntegration` - End-to-end integration (2 tests)

**Requirements**:
- Timer measures execution duration accurately
- Logs metrics in NDJSON format
- Calculates min/max/avg/p95 per agent
- Identifies top 3 slowest agents
- Prevents path traversal attacks (CWE-22)

---

### Phase 9: Model Downgrade (19 tests)
**File**: `test_phase9_model_downgrade.py`

Tests for downgrading 3 agents from Sonnet to Haiku model while maintaining quality.

**Key Test Classes**:
- `TestCommitMessageGeneratorHaikuFormat` - Conventional commits (5 tests)
- `TestAlignmentValidatorHaikuAccuracy` - Alignment detection >= 95% (5 tests)
- `TestProjectProgressTrackerHaikuGoalsUpdate` - Goal tracking (5 tests)
- `TestModelDowngradeIntegration` - Agent model verification (4 tests)

**Target Agents**:
- `commit-message-generator` - Sonnet → Haiku
- `alignment-validator` - Sonnet → Haiku
- `project-progress-tracker` - Sonnet → Haiku

**Quality Targets**:
- Conventional commit format compliance: 100%
- Alignment accuracy: >= 95%
- False positive rate: < 5%
- Cost savings: >= $0.25/month

---

### Phase 10: Prompt Streamlining (22 tests)
**File**: `test_phase10_prompt_streamlining.py`

Tests for extracting PROJECT.md template and streamlining agent prompts.

**Key Test Classes**:
- `TestProjectTemplateExtraction` - Template file structure (5 tests)
- `TestSetupWizardTemplateReference` - Streamlined setup-wizard (2 tests)
- `TestSetupWizardFunctionality` - /setup command still works (3 tests)
- `TestProjectBootstrapperStreamlining` - Reduced prompt size (3 tests)
- `TestProjectStatusAnalyzerStreamlining` - Maintained functionality (3 tests)
- `TestTokenReductionMeasurement` - Token savings >= 615 (3 tests)

**Target Reductions**:
- setup-wizard: 615 lines → 200 lines (67% reduction)
- project-bootstrapper: 20%+ reduction
- project-status-analyzer: 20%+ reduction

**Implementation**:
- Create `.claude/PROJECT.md-template.md`
- Update agents to reference template instead of inline content

---

### Phase 11: Partial Parallelization (28 tests)
**File**: `test_phase11_partial_parallelization.py`

Tests for enabling test-master and implementer agents to overlap execution.

**Key Test Classes**:
- `TestVerifyPartialParallelExecution` - Detect overlap (4 tests)
- `TestImplementerReceivesTestStructure` - Test handoff (3 tests)
- `TestPartialParallelizationQuality` - Quality maintained (4 tests)
- `TestWorkflowTimeReduction` - Time saved (4 tests)
- `TestTaskToolAgentInvocation` - Task tool invocation (4 tests)
- `TestPartialParallelizationCheckpoint` - Validation (4 tests)
- `TestPartialParallelizationIntegration` - End-to-end (5 tests)

**Timing Targets**:
- Overlap duration: 3-5 minutes
- Workflow time: 25 min → 18 min (12-28% reduction)
- Monthly savings: 150+ hours (for 30 workflows)

---

## Test Patterns

### Arrange-Act-Assert (AAA)
All tests follow the AAA pattern:

```python
def test_example(self):
    """Test description with expected behavior.

    Arrange: Setup test data
    Act: Execute code under test
    Assert: Verify expected behavior
    """
    # Arrange
    data = prepare_test_data()

    # Act
    result = function_under_test(data)

    # Assert
    assert result == expected_value
```

### Fixtures
Tests use pytest fixtures for reusable setup:

```python
@pytest.fixture
def sample_logs(tmp_path):
    """Create sample performance logs."""
    log_file = tmp_path / "metrics.json"
    # ... populate ...
    return log_file
```

### Mocking
External dependencies are mocked:

```python
@patch('module.external_function')
def test_with_mock(mock_function):
    mock_function.return_value = "mocked_result"
    # ... test code ...
```

---

## Current Status: TDD Red Phase

### Collection Results
```
4 errors during collection
0 items collected
```

**All test files fail to import** because implementation doesn't exist yet. This is expected in TDD red phase.

### Import Errors
- **Phase 8.5**: Missing `analyze_performance_logs` function
- **Phase 9**: Missing agent Python modules
- **Phase 10**: Missing `SetupWizard` class
- **Phase 11**: Missing `verify_parallel_validation()` method

---

## Next Steps

### When Implementing Phase 8.5
1. Create `analyze_performance_logs()` function
2. Implement `PerformanceMetrics` class
3. Add path validation for CWE-22
4. Re-run tests (should start passing)

### When Implementing Phase 9
1. Update agent YAML files with `model: haiku`
2. Create agent Python wrappers (if needed)
3. Verify output quality
4. Re-run tests

### When Implementing Phase 10
1. Create `.claude/PROJECT.md-template.md`
2. Streamline setup-wizard.md
3. Update other agents to reference template
4. Re-run tests

### When Implementing Phase 11
1. Add Task tool invocation in auto-implement.md
2. Implement test structure handoff
3. Add Checkpoint 4.1 validation
4. Implement parallel execution detection
5. Re-run tests

---

## Performance Targets

| Phase | Metric | Target | Test Name |
|-------|--------|--------|-----------|
| 8.5 | Timer overhead | < 5ms | `test_performance_timer_measures_execution_duration` |
| 8.5 | Path validation | < 1ms | `test_log_path_within_project_allowed` |
| 9 | Commit format | 100% | `test_commit_message_follows_conventional_format` |
| 9 | Alignment accuracy | >= 95% | `test_alignment_accuracy_rate` |
| 9 | Cost savings | >= $0.25/month | `test_combined_savings_across_3_agents` |
| 10 | Prompt reduction | 67% (615→200) | `test_setup_wizard_is_streamlined` |
| 10 | Token savings | >= 615 | `test_combined_token_savings` |
| 11 | Overlap duration | 3-5 min | `test_parallel_overlap_within_expected_duration` |
| 11 | Time reduction | >= 3 min | `test_time_reduction_17_percent_achieved` |
| 11 | Monthly savings | 150+ hours | `test_cumulative_monthly_time_savings` |

---

## Security Testing

All tests include security validation for CWE-22 (path traversal):

- `test_log_path_traversal_attack_blocked` - Blocks `../../etc/passwd`
- `test_log_path_symlink_attack_prevention` - Blocks symlink attacks
- `test_log_path_validation_rejects_null_bytes` - Rejects `\x00` injection
- `test_log_agent_name_validation` - Validates safe characters only
- `test_log_feature_no_newlines` - Rejects control characters

---

## Test Coverage

```
Phase 8.5: 27 tests
Phase 9:   19 tests
Phase 10:  22 tests
Phase 11:  28 tests
─────────────────
Total:     96 tests

Test Classes: 23
Fixtures: 12+
Mocks: Multiple
AAA Pattern: 100%
```

---

## Important Notes

1. **Tests are intentionally failing** - This is TDD red phase. Implementation will make tests pass.

2. **One test per requirement** - Each test validates a single requirement for clarity.

3. **Comprehensive coverage** - Tests cover happy path, edge cases, errors, and security.

4. **Performance measured** - Tests include performance assertions (timing, accuracy, cost).

5. **Security hardened** - Tests validate CWE-22 path traversal prevention.

---

## References

- Issue #46: Performance Optimization (Phases 8.5-11)
- `/tests/PHASE_8_PERFORMANCE_TESTS_SUMMARY.md` - Detailed test documentation
- `CLAUDE.md` - Project standards and conventions
- `PROJECT.md` - Project goals and scope

---

**Created**: 2025-11-13
**Agent**: test-master (TDD specialist)
**Status**: Red Phase - All 96 tests FAILING (expected)
