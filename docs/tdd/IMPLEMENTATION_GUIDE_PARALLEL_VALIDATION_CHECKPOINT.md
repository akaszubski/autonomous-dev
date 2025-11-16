# Implementation Guide: verify_parallel_validation() Checkpoint

**For**: Implementer Agent (Green Phase)
**Date**: 2025-11-09
**Status**: TDD Red Phase Complete → Ready for Implementation

---

## Quick Reference

**Goal**: Implement 4 methods in `scripts/agent_tracker.py` to make 23 tests pass

**Test file**: `tests/unit/test_verify_parallel_validation_checkpoint.py`

**Current status**: All 23 tests marked as `xfail` (expected to fail)

**Success criteria**: Remove `xfail` marker, run tests, see `23 passed`

---

## Implementation Checklist

### 1. Add verify_parallel_validation() Method

**Location**: `scripts/agent_tracker.py` (class AgentTracker)

**Insert after**: `verify_parallel_exploration()` method (around line 900)

**Pattern**: Copy-paste `verify_parallel_exploration()` and modify for 3 agents

**Key changes**:
- Find 3 agents: reviewer, security-auditor, doc-master
- Call `_detect_parallel_execution_three_agents()` instead of `_detect_parallel_execution()`
- Metadata key: `parallel_validation` (not `parallel_exploration`)
- Call `_record_incomplete_validation()` and `_record_failed_validation()` helpers

**Template**:
```python
def verify_parallel_validation(self) -> bool:
    """Verify parallel execution of reviewer, security-auditor, and doc-master agents.

    Returns:
        True if all 3 agents completed (parallel or sequential)
        False if agents incomplete or failed

    Side Effects:
        Writes parallel_validation metadata to session file

    Raises:
        ValueError: Invalid timestamp format or missing required fields
    """
    # Reload session data
    if self.session_file.exists():
        self.session_data = json.loads(self.session_file.read_text())

    # Initialize duplicate tracking
    self._duplicate_agents = []

    # Find the 3 validation agents
    reviewer = self._find_agent("reviewer")
    security = self._find_agent("security-auditor")
    doc_master = self._find_agent("doc-master")

    # Check completion status
    if not reviewer or not security or not doc_master:
        missing_agents = []
        if not reviewer:
            missing_agents.append("reviewer")
        if not security:
            missing_agents.append("security-auditor")
        if not doc_master:
            missing_agents.append("doc-master")

        self._record_incomplete_validation(missing_agents)
        return False

    # Check for failures
    if (reviewer["status"] != "completed" or
        security["status"] != "completed" or
        doc_master["status"] != "completed"):

        failed_agents = []
        incomplete_agents = []

        for agent, name in [(reviewer, "reviewer"),
                           (security, "security-auditor"),
                           (doc_master, "doc-master")]:
            if agent["status"] == "failed":
                failed_agents.append(name)
            elif agent["status"] != "completed":
                incomplete_agents.append(name)

        if failed_agents:
            self._record_failed_validation(failed_agents)
        else:
            self._record_incomplete_validation(incomplete_agents)
        return False

    # Calculate metrics
    reviewer_duration = reviewer.get("duration_seconds", 0)
    security_duration = security.get("duration_seconds", 0)
    doc_duration = doc_master.get("duration_seconds", 0)

    sequential_time = reviewer_duration + security_duration + doc_duration
    parallel_time = max(reviewer_duration, security_duration, doc_duration)
    time_saved = sequential_time - parallel_time
    efficiency = (time_saved / sequential_time * 100) if sequential_time > 0 else 0

    # Detect parallel vs sequential
    is_parallel = self._detect_parallel_execution_three_agents(reviewer, security, doc_master)
    status = "parallel" if is_parallel else "sequential"

    if not is_parallel:
        time_saved = 0
        efficiency = 0

    # Write metadata
    metrics = {
        "status": status,
        "sequential_time_seconds": sequential_time,
        "parallel_time_seconds": parallel_time,
        "time_saved_seconds": time_saved,
        "efficiency_percent": round(efficiency, 2)
    }

    if hasattr(self, '_duplicate_agents') and self._duplicate_agents:
        metrics["duplicate_agents"] = list(set(self._duplicate_agents))

    self.session_data["parallel_validation"] = metrics
    self._save()

    # Audit log
    audit_log("agent_tracker", "success", {
        "operation": "verify_parallel_validation",
        "status": status,
        "time_saved_seconds": time_saved,
        "efficiency_percent": round(efficiency, 2)
    })

    return True
```

---

### 2. Add _detect_parallel_execution_three_agents() Helper

**Location**: After `_detect_parallel_execution()` method (around line 950)

**Logic**: Check if maximum time difference between any pair of agents is < 5 seconds

**Template**:
```python
def _detect_parallel_execution_three_agents(
    self,
    agent1: Dict[str, Any],
    agent2: Dict[str, Any],
    agent3: Dict[str, Any]
) -> bool:
    """Detect if 3 agents ran in parallel (all start times within 5 seconds).

    Args:
        agent1: First agent data dict with 'started_at' timestamp
        agent2: Second agent data dict with 'started_at' timestamp
        agent3: Third agent data dict with 'started_at' timestamp

    Returns:
        True if all agents started within 5 seconds of each other, False otherwise
    """
    # Parse all start times
    start1 = datetime.fromisoformat(agent1["started_at"])
    start2 = datetime.fromisoformat(agent2["started_at"])
    start3 = datetime.fromisoformat(agent3["started_at"])

    # Calculate all pairwise time differences
    diff_1_2 = abs((start2 - start1).total_seconds())
    diff_1_3 = abs((start3 - start1).total_seconds())
    diff_2_3 = abs((start3 - start2).total_seconds())

    # Parallel if all pairs started within 5 seconds
    max_diff = max(diff_1_2, diff_1_3, diff_2_3)
    return max_diff < 5  # Note: < 5, not <= 5
```

---

### 3. Add _record_incomplete_validation() Helper

**Location**: After `_write_failed_status()` method (around line 980)

**Pattern**: Copy `_write_incomplete_status()` and rename

**Template**:
```python
def _record_incomplete_validation(self, missing_agents: List[str]):
    """Write incomplete validation status to session file.

    Args:
        missing_agents: List of agent names that didn't run
    """
    self.session_data["parallel_validation"] = {
        "status": "incomplete",
        "missing_agents": missing_agents
    }
    self._save()

    audit_log("agent_tracker", "failure", {
        "operation": "verify_parallel_validation",
        "status": "incomplete",
        "missing_agents": missing_agents
    })
```

---

### 4. Add _record_failed_validation() Helper

**Location**: After `_record_incomplete_validation()` method

**Pattern**: Copy `_write_failed_status()` and rename

**Template**:
```python
def _record_failed_validation(self, failed_agents: List[str]):
    """Write failed validation status to session file.

    Args:
        failed_agents: List of agent names that failed
    """
    self.session_data["parallel_validation"] = {
        "status": "failed",
        "failed_agents": failed_agents
    }
    self._save()

    audit_log("agent_tracker", "failure", {
        "operation": "verify_parallel_validation",
        "status": "failed",
        "failed_agents": failed_agents
    })
```

---

## Testing Strategy

### Step 1: Implement Methods

Add all 4 methods to `scripts/agent_tracker.py`

### Step 2: Remove xfail Marker

Edit `tests/unit/test_verify_parallel_validation_checkpoint.py`:

**Remove these lines** (at end of file):
```python
# Mark all tests as expecting to fail (TDD red phase)
pytestmark = pytest.mark.xfail(
    reason="TDD Red Phase: verify_parallel_validation() and helper methods not yet implemented. "
           "Tests verify expected behavior for parallel validation checkpoint."
)
```

### Step 3: Run Tests

```bash
# Run checkpoint tests only
pytest tests/unit/test_verify_parallel_validation_checkpoint.py -v

# Expected output: 23 passed

# Run full test suite (optional)
pytest tests/ -v
```

### Step 4: Verify Coverage

```bash
# Check coverage of new methods
pytest tests/unit/test_verify_parallel_validation_checkpoint.py --cov=scripts/agent_tracker --cov-report=term-missing

# Target: 95%+ coverage for new methods
```

---

## Common Issues & Solutions

### Issue: Tests still fail after implementation

**Check**:
1. Did you remove the `pytestmark = pytest.mark.xfail` line?
2. Are method signatures exactly as specified?
3. Are you using `< 5` (not `<= 5`) for threshold?
4. Are you handling missing `duration_seconds` fields (default to 0)?

### Issue: Import errors

**Solution**: Methods should be in `AgentTracker` class, no new imports needed

### Issue: Metrics calculation wrong

**Check**:
- Sequential time = sum of all 3 durations
- Parallel time = max of all 3 durations
- Time saved = sequential - parallel (but 0 if sequential execution)
- Efficiency = (time_saved / sequential) * 100

### Issue: Session file format wrong

**Check**: Metadata key must be `"parallel_validation"` (not `"parallel_exploration"`)

---

## Validation Checklist

- [ ] All 4 methods added to `scripts/agent_tracker.py`
- [ ] Methods follow exact signatures from this guide
- [ ] Removed `xfail` marker from test file
- [ ] All 23 tests pass
- [ ] Coverage >= 95% for new methods
- [ ] No new imports required
- [ ] Audit logging works (check `logs/security_audit.log`)
- [ ] Session file metadata format correct

---

## Example Session File Output

After successful parallel validation:

```json
{
  "session_id": "20251109-test",
  "started": "2025-11-09T10:00:00",
  "agents": [
    {
      "agent": "reviewer",
      "status": "completed",
      "started_at": "2025-11-09T10:05:00",
      "completed_at": "2025-11-09T10:07:00",
      "duration_seconds": 120
    },
    {
      "agent": "security-auditor",
      "status": "completed",
      "started_at": "2025-11-09T10:05:02",
      "completed_at": "2025-11-09T10:07:32",
      "duration_seconds": 150
    },
    {
      "agent": "doc-master",
      "status": "completed",
      "started_at": "2025-11-09T10:05:04",
      "completed_at": "2025-11-09T10:06:44",
      "duration_seconds": 100
    }
  ],
  "parallel_validation": {
    "status": "parallel",
    "sequential_time_seconds": 370,
    "parallel_time_seconds": 150,
    "time_saved_seconds": 220,
    "efficiency_percent": 59.46
  }
}
```

---

## Final Verification

Run the TDD verification script after implementation:

```bash
python tests/verify_parallel_validation_checkpoint_tdd.py
```

**Expected output**: Should show "Implementation complete" or similar success message

---

**Ready to implement? Start with method #1 (verify_parallel_validation) and work through the checklist!**
