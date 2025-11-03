# Progress Indicator Test Suite

**Created**: 2025-11-04
**Status**: Tests written (TDD) - Implementation pending
**Coverage Target**: 80%+

This document describes the comprehensive test suite for the real-time progress indicator system.

---

## Overview

Following Test-Driven Development (TDD), we've written tests **before** implementation. All tests will fail initially until the components are implemented.

### Test Files Created

1. **`tests/unit/test_progress_display.py`** (496 lines)
   - Tests for `progress_display.py` (terminal UI)
   - 40+ test cases covering rendering, TTY modes, progress calculation

2. **`tests/unit/test_pipeline_controller.py`** (425 lines)
   - Tests for `pipeline_controller.py` (process lifecycle)
   - 35+ test cases covering subprocess management, cleanup, signals

3. **`tests/integration/test_progress_integration.py`** (493 lines)
   - End-to-end integration tests
   - 25+ test cases covering full pipeline workflows

4. **`tests/unit/test_agent_tracker_enhancements.py`** (389 lines)
   - Tests for new features in `agent_tracker.py`
   - 35+ test cases for display metadata, progress calculation

5. **`tests/fixtures/progress_fixtures.py`** (402 lines)
   - Shared test fixtures and helper functions
   - Mock data generators, assertion helpers

**Total**: ~2,200 lines of test code covering all aspects of the progress system

---

## Test Coverage

### Unit Tests: `test_progress_display.py`

**Rendering Tests**:
- ✅ Basic tree view rendering
- ✅ Progress bar display (0-100%)
- ✅ Empty pipeline state
- ✅ Complete pipeline state
- ✅ Failed agent display
- ✅ GitHub issue display
- ✅ Agent duration display
- ✅ Tools used display

**TTY Mode Tests**:
- ✅ TTY mode detection
- ✅ ANSI escape codes in TTY mode
- ✅ No ANSI codes in non-TTY mode
- ✅ Incremental updates in non-TTY mode

**Progress Calculation**:
- ✅ Empty pipeline (0%)
- ✅ Partial completion (1-99%)
- ✅ Full completion (100%)
- ✅ Running agents contribute partial progress
- ✅ Failed agents count as complete

**JSON Handling**:
- ✅ Valid JSON loading
- ✅ File not found
- ✅ Malformed JSON
- ✅ Empty file
- ✅ Permission errors

**Terminal Resize**:
- ✅ Adapt to terminal size
- ✅ Minimum width handling
- ✅ Line wrapping/truncation

**Display Loop**:
- ✅ Polling mechanism
- ✅ Refresh rate
- ✅ Stop on completion
- ✅ Keyboard interrupt handling

**Formatting**:
- ✅ Duration formatting (s, m, h)
- ✅ Message truncation
- ✅ Agent ordering

### Unit Tests: `test_pipeline_controller.py`

**Initialization**:
- ✅ Controller setup
- ✅ PID file path creation

**Process Management**:
- ✅ Start display subprocess
- ✅ Write PID file
- ✅ Pass session file argument
- ✅ Detached process execution
- ✅ Prevent duplicate processes
- ✅ Handle stale PID files

**Stopping Display**:
- ✅ Graceful shutdown (SIGTERM)
- ✅ Wait for exit
- ✅ Force kill after timeout
- ✅ Remove PID file
- ✅ Handle already-stopped process

**PID File Operations**:
- ✅ Read PID from file
- ✅ Handle missing file
- ✅ Handle invalid content
- ✅ Check if process running
- ✅ Handle permission errors

**Cleanup**:
- ✅ Cleanup on error
- ✅ Cleanup on signal
- ✅ Context manager cleanup
- ✅ Atexit cleanup

**Signal Handling**:
- ✅ Register signal handlers
- ✅ SIGTERM handler
- ✅ SIGINT handler
- ✅ Handler stops display

**Error Handling**:
- ✅ File not found
- ✅ Permission errors
- ✅ Process disappears

**Monitoring**:
- ✅ Check display health
- ✅ Restart on crash
- ✅ Get status information

### Integration Tests: `test_progress_integration.py`

**Full Pipeline**:
- ✅ Complete workflow with display
- ✅ Display updates as agents complete
- ✅ Incremental progress
- ✅ Completion detection

**Error Recovery**:
- ✅ Recovery from display crash
- ✅ Corrupted session file handling
- ✅ Agent failure handling
- ✅ Cleanup after errors

**Concurrent Access**:
- ✅ Concurrent agent updates
- ✅ Multiple display prevention
- ✅ File locking

**Performance**:
- ✅ Many agents (100+)
- ✅ Polling interval efficiency

**End-to-End Workflows**:
- ✅ Complete /auto-implement flow
- ✅ GitHub issue tracking
- ✅ Session persistence
- ✅ Display restart

**Edge Cases**:
- ✅ Very long messages
- ✅ Unicode and emojis
- ✅ Missing fields

### Unit Tests: `test_agent_tracker_enhancements.py`

**Progress Calculation**:
- ✅ Empty pipeline
- ✅ Partial completion
- ✅ Full completion
- ✅ Running agent partial credit
- ✅ Failed agent handling

**Expected Agents**:
- ✅ Get expected agent list
- ✅ Verify execution order

**Display Metadata**:
- ✅ Basic metadata generation
- ✅ Include pending agents
- ✅ Agent descriptions
- ✅ Estimated time remaining
- ✅ Status emojis

**Tree View Data**:
- ✅ Data structure for tree view
- ✅ Agent nesting/hierarchy
- ✅ Tools used display

**Time Estimation**:
- ✅ No data baseline
- ✅ Average-based estimation
- ✅ Account for running agents
- ✅ Average duration calculation

**Status Helpers**:
- ✅ Is pipeline complete
- ✅ Get pending agents
- ✅ Get running agent
- ✅ Handle multiple running (error)

**Display Formatting**:
- ✅ Format agent names
- ✅ Get status emojis
- ✅ Get status colors

**GitHub Integration**:
- ✅ Include issue in metadata
- ✅ Format issue URL

---

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r plugins/autonomous-dev/requirements-dev.txt
```

### Run All Tests

```bash
# Run all progress indicator tests
pytest tests/unit/test_progress_display.py \
       tests/unit/test_pipeline_controller.py \
       tests/unit/test_agent_tracker_enhancements.py \
       tests/integration/test_progress_integration.py -v

# Run with coverage
pytest tests/unit/test_progress_display.py \
       tests/unit/test_pipeline_controller.py \
       tests/unit/test_agent_tracker_enhancements.py \
       tests/integration/test_progress_integration.py \
       --cov=plugins.autonomous_dev.scripts \
       --cov-report=html
```

### Run Individual Test Files

```bash
# Unit tests - progress display
pytest tests/unit/test_progress_display.py -v

# Unit tests - pipeline controller
pytest tests/unit/test_pipeline_controller.py -v

# Unit tests - agent tracker enhancements
pytest tests/unit/test_agent_tracker_enhancements.py -v

# Integration tests
pytest tests/integration/test_progress_integration.py -v
```

### Run Specific Tests

```bash
# Test specific feature
pytest tests/unit/test_progress_display.py::TestProgressDisplay::test_render_tree_view_basic -v

# Test specific class
pytest tests/unit/test_pipeline_controller.py::TestPipelineController -v
```

---

## Expected Test Results (Pre-Implementation)

### Current Status

All tests will **FAIL** with `ImportError` or `ModuleNotFoundError` because:

1. `plugins/autonomous_dev/scripts/progress_display.py` - **Not implemented yet**
2. `plugins/autonomous_dev/scripts/pipeline_controller.py` - **Not implemented yet**
3. Enhancements to `scripts/agent_tracker.py` - **Not implemented yet**

### Example Failure Output

```
ImportError: cannot import name 'ProgressDisplay' from 'plugins.autonomous_dev.scripts.progress_display'
```

This is **expected** in TDD! Tests drive implementation.

### Post-Implementation Goals

Once implemented, expect:

- **Total tests**: ~135 test cases
- **Coverage**: 80%+ for all three modules
- **Pass rate**: 100%
- **Performance**: All tests complete in < 30 seconds

---

## Test Fixtures

### Shared Fixtures (`tests/fixtures/progress_fixtures.py`)

**Mock Data Generators**:
- `create_mock_pipeline_state()` - Generate pipeline state
- `create_agent_entry()` - Generate agent entry
- `create_complete_pipeline()` - Full pipeline (all agents done)
- `create_partial_pipeline()` - Partial pipeline (N agents done)
- `create_failed_pipeline()` - Pipeline with failure

**File Helpers**:
- `write_pipeline_state()` - Write state to file
- `read_pipeline_state()` - Read state from file
- `update_agent_status()` - Update specific agent

**Simulation Helpers**:
- `simulate_agent_completion()` - Simulate agent completing
- `simulate_agent_failure()` - Simulate agent failing
- `simulate_full_pipeline()` - Simulate complete workflow

**Assertion Helpers**:
- `assert_agent_status()` - Check agent status
- `assert_pipeline_complete()` - Check all agents done
- `assert_no_failures()` - Check no failures
- `get_agent_count_by_status()` - Count by status
- `get_total_duration()` - Sum durations

**Constants**:
- `EXPECTED_AGENT_ORDER` - Standard execution order
- `EXPECTED_AGENT_COUNT` - 7 agents
- `STATUS_EMOJIS` - Emoji mappings
- `MIN_DURATIONS` - Performance thresholds

### Using Fixtures in Tests

```python
from tests.fixtures.progress_fixtures import (
    create_complete_pipeline,
    simulate_agent_completion
)

def test_example(tmp_path):
    session_file = tmp_path / "session.json"

    # Create complete pipeline state
    state = create_complete_pipeline(github_issue=42)
    write_pipeline_state(session_file, state)

    # Assert
    assert_pipeline_complete(state)
```

---

## Implementation Checklist

Use tests to guide implementation:

### 1. `progress_display.py`

- [ ] `ProgressDisplay` class
- [ ] `load_pipeline_state()` method
- [ ] `render_tree_view()` method
- [ ] `calculate_progress()` method
- [ ] `is_pipeline_complete()` method
- [ ] `format_duration()` method
- [ ] TTY mode detection
- [ ] ANSI escape code handling
- [ ] Terminal resize handling
- [ ] Display loop with polling
- [ ] Graceful error handling

### 2. `pipeline_controller.py`

- [ ] `PipelineController` class
- [ ] `start_display()` method
- [ ] `stop_display()` method
- [ ] `is_display_running()` method
- [ ] PID file management
- [ ] Signal handler registration
- [ ] Cleanup on exit
- [ ] Context manager support
- [ ] Process health monitoring
- [ ] Error recovery

### 3. `agent_tracker.py` Enhancements

- [ ] `calculate_progress()` method
- [ ] `get_expected_agents()` method
- [ ] `get_display_metadata()` method
- [ ] `get_tree_view_data()` method
- [ ] `estimate_remaining_time()` method
- [ ] `get_average_agent_duration()` method
- [ ] `is_pipeline_complete()` method
- [ ] `get_pending_agents()` method
- [ ] `get_running_agent()` method
- [ ] `format_agent_name()` method
- [ ] `get_agent_emoji()` method
- [ ] `get_agent_color()` method

---

## TDD Workflow

### Red-Green-Refactor Cycle

1. **RED**: Run tests → All fail (current state)
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve code quality while keeping tests green

### Implementation Steps

For each component:

```bash
# 1. Run tests (should fail)
pytest tests/unit/test_progress_display.py -v

# 2. Implement one feature at a time
vim plugins/autonomous-dev/scripts/progress_display.py

# 3. Run tests again (some should pass)
pytest tests/unit/test_progress_display.py -v

# 4. Repeat until all tests pass
```

### Test-First Benefits

- ✅ Clear requirements from tests
- ✅ Confidence in correctness
- ✅ Catch regressions immediately
- ✅ Better API design
- ✅ Living documentation

---

## Coverage Goals

### Minimum Coverage Targets

- **`progress_display.py`**: 80%+
- **`pipeline_controller.py`**: 80%+
- **`agent_tracker.py` (new methods)**: 80%+

### Coverage Report

```bash
# Generate HTML coverage report
pytest tests/unit/test_progress_display.py \
       tests/unit/test_pipeline_controller.py \
       tests/unit/test_agent_tracker_enhancements.py \
       --cov=plugins.autonomous_dev.scripts \
       --cov-report=html

# View report
open htmlcov/index.html
```

---

## Maintenance

### Adding New Tests

When adding features:

1. Write test first (TDD)
2. Place in appropriate test file
3. Use existing fixtures where possible
4. Follow naming convention: `test_<feature>_<scenario>`

### Test Naming Convention

```python
# Good test names (describe what and when)
def test_render_tree_view_with_failed_agent():
def test_stop_display_sends_sigterm():
def test_calculate_progress_empty_pipeline():

# Bad test names (unclear)
def test_display():
def test_controller():
def test_tracker():
```

### Updating Tests

When changing requirements:

1. Update tests to reflect new behavior
2. Run tests to verify failures
3. Update implementation
4. Verify all tests pass

---

## Troubleshooting

### Import Errors

```
ImportError: cannot import name 'ProgressDisplay'
```

**Solution**: This is expected pre-implementation. Create the module:

```bash
touch plugins/autonomous-dev/scripts/progress_display.py
```

### Fixture Not Found

```
fixture 'mock_pipeline_state' not found
```

**Solution**: Import fixture from conftest or use built-in fixtures:

```python
from tests.fixtures.progress_fixtures import create_mock_pipeline_state
```

### Test Timeouts

If tests hang:

```bash
# Run with timeout
pytest tests/unit/test_progress_display.py --timeout=10
```

Check for:
- Infinite loops in display polling
- Subprocess not terminating
- File locks not releasing

---

## Next Steps

1. **Implement**: Use tests to guide implementation
2. **Verify**: Run tests frequently during development
3. **Coverage**: Check coverage after implementation
4. **Integration**: Run integration tests last
5. **Document**: Update docs based on final implementation

---

## Related Documentation

- **Planning**: See planner's architecture document
- **Agent Tracker**: See `scripts/agent_tracker.py`
- **Testing Guide**: See `tests/README.md`
- **TDD Methodology**: See global CLAUDE.md testing section

---

**Tests are complete and ready for implementation!**

Follow TDD cycle: Run tests (RED) → Implement (GREEN) → Refactor → Repeat
