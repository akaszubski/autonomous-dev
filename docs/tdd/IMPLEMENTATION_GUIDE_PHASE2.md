# Implementation Guide: Issue #46 Phase 2

**For**: implementer agent
**Date**: 2025-11-07
**Status**: Tests written (RED phase) - ready for implementation

## Quick Start

1. **Read**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/TEST_SUMMARY_PHASE2.md`
2. **Implement**: `verify_parallel_exploration()` in `scripts/agent_tracker.py`
3. **Update**: `commands/auto-implement.md` STEP 1-2 for parallel execution
4. **Verify**: Run tests and watch them turn GREEN

## Implementation Checklist

### Step 1: Implement verify_parallel_exploration()

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/agent_tracker.py`

**Location**: Add as new method in `AgentTracker` class (around line 500)

**Signature**:
```python
def verify_parallel_exploration(self) -> bool:
    """Verify parallel execution of researcher and planner agents."""
```

**Requirements** (from tests):

1. **Read session file** and find researcher + planner agents
   - Handle case: agents not found → return False, log "incomplete"
   - Handle case: agents failed → return False, log "failed"

2. **Validate timing data**
   - Check for missing timestamps → raise ValueError
   - Check for invalid timestamp format → raise ValueError
   - Parse ISO format timestamps: `datetime.fromisoformat()`

3. **Detect parallel vs sequential**
   - Parallel: start times within 5 seconds
   - Sequential: start times > 5 seconds apart
   - Log status: "parallel" or "sequential"

4. **Calculate metrics**
   ```python
   sequential_time = researcher_duration + planner_duration
   parallel_time = max(researcher_duration, planner_duration)
   time_saved = sequential_time - parallel_time
   efficiency = (time_saved / sequential_time) * 100
   ```

5. **Write metrics to session file**
   ```python
   session_data["parallel_exploration"] = {
       "status": "parallel" | "sequential" | "incomplete" | "failed",
       "sequential_time_seconds": int,
       "parallel_time_seconds": int,
       "time_saved_seconds": int,
       "efficiency_percent": float,
       "missing_agents": [],  # if incomplete
       "failed_agents": []     # if failed
   }
   ```

6. **Return result**
   - True: Both completed (parallel or sequential)
   - False: Incomplete or failed

**Edge Cases to Handle**:
- Duplicate agent entries → use latest completed
- Missing timestamps → raise ValueError
- Invalid timestamp format → raise ValueError
- Empty session file → return False
- Clock skew (planner starts before researcher) → detect and log warning

**Security Requirements**:
- Use existing `validate_path()` for session file path
- Use `audit_log()` for security events
- All security utils already in place from Issue #46 Phase 1

### Step 2: Update auto-implement.md STEP 1-2

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/commands/auto-implement.md`

**Current** (Sequential):
```markdown
**STEP 1**: Invoke researcher agent (6 minutes)
**STEP 2**: Invoke planner agent (7 minutes)
```

**New** (Parallel):
```markdown
**STEP 1-2**: Invoke researcher and planner in parallel (7 minutes, saves 6 minutes)

Execute in single response with 2 Task tool calls:
1. Task(agent="researcher", instruction="Research patterns and best practices")
2. Task(agent="planner", instruction="Create architecture plan")

Both agents run concurrently. Wait for both to complete.

After completion:
- Verify parallel execution: `verify_parallel_exploration()`
- If verification succeeds: Proceed to STEP 3
- If verification fails: Fall back to sequential re-execution

Expected time savings: 3-8 minutes (depending on agent durations)
```

**Graceful Fallback**:
```markdown
If parallel execution fails:
1. Log failure reason
2. Re-invoke researcher sequentially
3. Wait for completion
4. Re-invoke planner sequentially
5. Proceed to STEP 3
```

### Step 3: Run Tests

**Unit Tests** (fast, ~1 second):
```bash
pytest tests/unit/test_parallel_exploration_logic.py -v
```

**Integration Tests** (moderate, ~5 seconds):
```bash
pytest tests/integration/test_parallel_research_planning.py -v
```

**Security Tests** (fast, ~1 second):
```bash
pytest tests/security/test_parallel_execution_security.py -v
```

**Performance Tests** (extended, ~5-10 minutes):
```bash
pytest tests/regression/extended/test_performance_phase2_parallelization.py -v --extended
```

**All Tests**:
```bash
pytest tests/unit/test_parallel_exploration_logic.py \
       tests/integration/test_parallel_research_planning.py \
       tests/security/test_parallel_execution_security.py \
       tests/regression/extended/test_performance_phase2_parallelization.py \
       -v
```

**Expected Results After Implementation**:
- 29 FAILED → 29 PASSED (or more if skipped tests now run)
- 29 SKIPPED → Some may become runnable
- 1 PASSED → Should remain passed

### Step 4: Verify Coverage

```bash
pytest tests/unit/test_parallel_exploration_logic.py \
       --cov=scripts.agent_tracker \
       --cov-report=html \
       --cov-report=term
```

**Target**: 100% coverage of `verify_parallel_exploration()` function

## Test Patterns to Follow

**Test Structure** (all tests follow this):
```python
def test_scenario_name(self, fixtures):
    """
    Test description.

    Given: Initial conditions
    When: Action performed
    Then: Expected outcome
    And: Additional validations

    Protects: What this test prevents from breaking
    """
    # Arrange: Setup test conditions
    # Act: Execute the code under test
    # Assert: Verify expected outcomes
```

**Given/When/Then Comments**:
Every test has clear GWT comments explaining the test scenario.

**Clear Assertions**:
```python
assert result is True, "Expected parallel exploration to succeed"
```

## Common Test Failures and Fixes

### AttributeError: 'AgentTracker' object has no attribute 'verify_parallel_exploration'

**Cause**: Function not implemented yet
**Fix**: Implement `verify_parallel_exploration()` in `AgentTracker` class

### ValueError: Invalid timestamp format

**Cause**: Timestamp parsing fails
**Fix**: Use `datetime.fromisoformat()` with try/except
```python
try:
    started_at = datetime.fromisoformat(agent_data["started_at"])
except (ValueError, KeyError) as e:
    raise ValueError(f"Invalid timestamp format: {e}")
```

### ValueError: Missing timestamp

**Cause**: Session file missing "started_at" or "completed_at"
**Fix**: Validate required fields exist before parsing
```python
if "started_at" not in agent_data or "completed_at" not in agent_data:
    raise ValueError(f"Missing timestamp for {agent_data['agent']}")
```

### AssertionError: Time saved calculation incorrect

**Cause**: Math error in metrics calculation
**Fix**: Double-check formula
```python
sequential_time = researcher_duration + planner_duration
parallel_time = max(researcher_duration, planner_duration)
time_saved = sequential_time - parallel_time  # Should be positive
```

### AssertionError: Efficiency percentage incorrect

**Cause**: Division error or percentage calculation
**Fix**: Use correct formula
```python
efficiency_percent = (time_saved / sequential_time) * 100
# Example: (6 / 13) * 100 = 46.15%
```

## Example Implementation Skeleton

```python
def verify_parallel_exploration(self) -> bool:
    """
    Verify parallel execution of researcher and planner agents.

    Returns:
        True if both agents completed successfully
        False if incomplete or failed

    Raises:
        ValueError: Invalid timestamp format or missing required fields
    """
    # 1. Read session file
    session_data = self._read_session_file()

    # 2. Find researcher and planner agents
    researcher = self._find_agent(session_data, "researcher")
    planner = self._find_agent(session_data, "planner")

    # 3. Check completion status
    if not researcher or not planner:
        self._write_incomplete_status(session_data, researcher, planner)
        return False

    if researcher["status"] != "completed" or planner["status"] != "completed":
        self._write_failed_status(session_data, researcher, planner)
        return False

    # 4. Validate timing data
    self._validate_timestamps(researcher, planner)

    # 5. Calculate metrics
    metrics = self._calculate_metrics(researcher, planner)

    # 6. Detect parallel vs sequential
    is_parallel = self._detect_parallel_execution(researcher, planner)
    metrics["status"] = "parallel" if is_parallel else "sequential"

    # 7. Write metrics to session file
    session_data["parallel_exploration"] = metrics
    self._write_session_file(session_data)

    # 8. Log result
    self._log_verification_result(metrics)

    return True


def _find_agent(self, session_data: dict, agent_name: str) -> Optional[dict]:
    """Find agent in session data, return latest completed entry."""
    agents = [a for a in session_data.get("agents", []) if a["agent"] == agent_name]
    if not agents:
        return None
    # Return latest completed, or last entry
    completed = [a for a in agents if a["status"] == "completed"]
    return completed[-1] if completed else agents[-1]


def _validate_timestamps(self, researcher: dict, planner: dict):
    """Validate timestamps are present and valid ISO format."""
    for agent, data in [("researcher", researcher), ("planner", planner)]:
        if "started_at" not in data or "completed_at" not in data:
            raise ValueError(f"Missing timestamp for {agent}")
        try:
            datetime.fromisoformat(data["started_at"])
            datetime.fromisoformat(data["completed_at"])
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format for {agent}: {e}")


def _calculate_metrics(self, researcher: dict, planner: dict) -> dict:
    """Calculate parallelization metrics."""
    researcher_duration = researcher.get("duration_seconds", 0)
    planner_duration = planner.get("duration_seconds", 0)

    sequential_time = researcher_duration + planner_duration
    parallel_time = max(researcher_duration, planner_duration)
    time_saved = sequential_time - parallel_time
    efficiency = (time_saved / sequential_time * 100) if sequential_time > 0 else 0

    return {
        "sequential_time_seconds": sequential_time,
        "parallel_time_seconds": parallel_time,
        "time_saved_seconds": time_saved,
        "efficiency_percent": round(efficiency, 2)
    }


def _detect_parallel_execution(self, researcher: dict, planner: dict) -> bool:
    """Detect if agents ran in parallel (start times within 5 seconds)."""
    researcher_start = datetime.fromisoformat(researcher["started_at"])
    planner_start = datetime.fromisoformat(planner["started_at"])

    time_diff = abs((planner_start - researcher_start).total_seconds())
    return time_diff < 5  # Parallel if started within 5 seconds
```

## Performance Targets

Based on tests, implementation must achieve:

1. **Time Savings**: 3-8 minutes per /auto-implement
   - Baseline sequential: 13 minutes (6 + 7)
   - Target parallel: 7 minutes (max of 6, 7)
   - Savings: 6 minutes

2. **Efficiency**: ≥50% average
   - Formula: (time_saved / sequential_time) * 100
   - Example: (6 / 13) * 100 = 46.15%

3. **Full Pipeline**: ≤25 minutes total
   - STEP 1-2 (parallel): 7 min
   - STEP 3 (test-master): 5 min
   - STEP 4 (implementer): 10 min
   - STEP 5-7 (parallel validation): 5 min
   - Total: 27 minutes (target: ≤25 with optimization)

## Security Reminders

- **Path Traversal**: Use `validate_path()` from security_utils
- **Input Validation**: Use `validate_agent_name()` from security_utils
- **Audit Logging**: Use `audit_log()` for security events
- **Atomic Writes**: Session file writes already atomic (existing implementation)

## Questions?

Check the test files for detailed examples:
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_parallel_exploration_logic.py`
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_parallel_research_planning.py`

Every test has clear Given/When/Then comments explaining the expected behavior.

## Success Criteria

✅ All 29 failing tests now pass
✅ Coverage ≥95% for verify_parallel_exploration()
✅ No new security vulnerabilities introduced
✅ Performance targets met (3-8 min savings)
✅ Graceful fallback to sequential works
✅ Documentation updated in auto-implement.md

---

**Ready to implement!** Tests are waiting for you to make them pass. 🚀
