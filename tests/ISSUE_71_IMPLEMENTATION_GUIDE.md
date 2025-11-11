# Issue #71 Implementation Guide

**Date**: 2025-11-11
**Feature**: Fix verify_parallel_exploration() Task tool agent detection
**For**: implementer agent
**Status**: Ready for implementation (TDD red phase complete)

---

## Quick Start

### 1. Run Tests (Should FAIL)
```bash
# Verify tests fail (TDD red phase)
python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py -v
python -m pytest tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v

# Expected: 33 failures (methods don't exist yet)
```

### 2. Implement Methods (Make Tests Pass)
**File to Edit**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/agent_tracker.py`

**Methods to Add** (5 new methods):
1. `_detect_agent_from_session_text()`
2. `_detect_agent_from_json_structure()`
3. `_validate_agent_data()`
4. `_get_session_text_file()`
5. Enhanced `_find_agent()` (modify existing)

### 3. Verify Tests Pass
```bash
# Run tests again
python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py -v
python -m pytest tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v

# Expected: 33 passing (all green)
```

---

## Method Implementation Order

### Priority 1: Helper Methods (Foundation)

#### Method 1: `_validate_agent_data(agent_data: Dict) -> bool`
**Purpose**: Validate agent data structure

**Requirements**:
- Check required fields: `agent`, `status`, `started_at`, `completed_at`
- Validate status in `["completed", "failed"]`
- Validate ISO timestamp format (try `datetime.fromisoformat()`)
- Return `True` if valid, `False` otherwise
- No exceptions (graceful validation)

**Tests**: 4 tests in `TestDataValidation`

**Implementation Hint**:
```python
def _validate_agent_data(self, agent_data: Dict[str, Any]) -> bool:
    """Validate agent data structure and timestamps."""
    # Check required fields
    required_fields = ["agent", "status", "started_at", "completed_at"]
    if not all(field in agent_data for field in required_fields):
        return False

    # Validate status
    if agent_data["status"] not in ["completed", "failed"]:
        return False

    # Validate timestamps (ISO format)
    try:
        datetime.fromisoformat(agent_data["started_at"])
        datetime.fromisoformat(agent_data["completed_at"])
    except (ValueError, TypeError):
        return False

    return True
```

---

#### Method 2: `_get_session_text_file() -> Optional[str]`
**Purpose**: Derive session text file path from JSON file

**Requirements**:
- Given: `self.session_file = "/path/to/20251111-test.json"`
- Derive: `"/path/to/20251111-test-session.md"`
- Check file exists
- Return path string or `None`

**Tests**: Implicit in other tests (used by `_detect_agent_from_session_text`)

**Implementation Hint**:
```python
def _get_session_text_file(self) -> Optional[str]:
    """Get session text file path (.md) from JSON file path."""
    # Derive .md file path
    json_path = Path(self.session_file)
    text_path = json_path.parent / f"{json_path.stem}-session.md"

    # Check exists
    if text_path.exists():
        return str(text_path)

    return None
```

---

### Priority 2: Detection Methods (Core Logic)

#### Method 3: `_detect_agent_from_session_text(agent_name: str, session_text_path: str) -> Optional[Dict]`
**Purpose**: Parse session .md file for agent completion markers

**Requirements**:
- Read session text file (.md format)
- Find completion marker: `**HH:MM:SS - agent_name**: ... completed`
- Extract start timestamp (agent start line)
- Extract completion timestamp (completion line)
- Calculate duration if possible
- Return agent data dict or `None`
- Handle missing files, invalid formats gracefully

**Tests**: 5 tests in `TestSessionTextParser`

**Implementation Hint**:
```python
def _detect_agent_from_session_text(
    self,
    agent_name: str,
    session_text_path: str
) -> Optional[Dict[str, Any]]:
    """Parse session text file for agent completion markers.

    Format: **HH:MM:SS - agent_name**: message
    """
    try:
        # Validate path (security)
        from security_utils import validate_path
        validate_path(session_text_path, allow_outside_project=False)

        # Read file
        text_path = Path(session_text_path)
        if not text_path.exists():
            return None

        content = text_path.read_text()

        # Find agent markers (regex)
        import re
        # Pattern: **HH:MM:SS - agent_name**: message
        pattern = rf"\*\*(\d{{2}}:\d{{2}}:\d{{2}}) - {re.escape(agent_name)}\*\*: (.+)"
        matches = re.findall(pattern, content)

        if not matches:
            return None

        # Find completion marker
        completion_marker = None
        start_marker = None

        for time_str, message in matches:
            if "completed" in message.lower() or "complete" in message.lower():
                completion_marker = (time_str, message)
            else:
                start_marker = (time_str, message)

        if not completion_marker:
            return None

        # Parse timestamps
        # Get session date from file
        date_match = re.search(r"Session (\d{{8}})", content)
        if not date_match:
            return None

        session_date = date_match.group(1)  # e.g., "20251111"

        # Convert to ISO format
        start_time_str = f"{session_date[:4]}-{session_date[4:6]}-{session_date[6:8]}T{start_marker[0] if start_marker else completion_marker[0]}"
        complete_time_str = f"{session_date[:4]}-{session_date[4:6]}-{session_date[6:8]}T{completion_marker[0]}"

        # Build agent data
        agent_data = {
            "agent": agent_name,
            "status": "completed",
            "started_at": start_time_str,
            "completed_at": complete_time_str,
            "message": completion_marker[1]
        }

        # Calculate duration if both timestamps available
        if start_marker:
            try:
                start_dt = datetime.fromisoformat(start_time_str)
                complete_dt = datetime.fromisoformat(complete_time_str)
                duration = int((complete_dt - start_dt).total_seconds())
                agent_data["duration_seconds"] = duration
            except ValueError:
                pass  # Duration calculation failed, skip

        # Validate before returning
        if not self._validate_agent_data(agent_data):
            return None

        return agent_data

    except Exception as e:
        # Log error but don't crash
        audit_log("agent_tracker", "error", {
            "operation": "_detect_agent_from_session_text",
            "agent_name": agent_name,
            "error": str(e)
        })
        return None
```

---

#### Method 4: `_detect_agent_from_json_structure(agent_name: str) -> Optional[Dict]`
**Purpose**: Reload JSON file to detect external modifications

**Requirements**:
- Reload JSON file from disk (don't use cached `self.session_data`)
- Find agent with `status="completed"`
- Validate timestamps
- Return agent data dict or `None`
- Handle missing agents, corrupted JSON gracefully

**Tests**: 4 tests in `TestJSONStructureAnalyzer`

**Implementation Hint**:
```python
def _detect_agent_from_json_structure(
    self,
    agent_name: str
) -> Optional[Dict[str, Any]]:
    """Reload JSON file to detect external modifications."""
    try:
        # Reload from disk (detect external changes)
        if not self.session_file.exists():
            return None

        # Parse JSON
        try:
            session_data = json.loads(self.session_file.read_text())
        except json.JSONDecodeError:
            return None  # Corrupted JSON

        # Find agent
        agents = [a for a in session_data.get("agents", []) if a["agent"] == agent_name]
        if not agents:
            return None

        # Get latest entry
        agent_data = agents[-1]

        # Must be completed
        if agent_data.get("status") != "completed":
            return None

        # Validate data
        if not self._validate_agent_data(agent_data):
            return None

        return agent_data

    except Exception as e:
        # Log error but don't crash
        audit_log("agent_tracker", "error", {
            "operation": "_detect_agent_from_json_structure",
            "agent_name": agent_name,
            "error": str(e)
        })
        return None
```

---

### Priority 3: Enhanced _find_agent() (Integration)

#### Method 5: Enhanced `_find_agent(agent_name: str) -> Optional[Dict]`
**Purpose**: Multi-method detection with priority fallback

**Requirements**:
- **Priority 1**: Check tracker (existing behavior)
- **Priority 2**: Check JSON structure (new)
- **Priority 3**: Parse session text (new)
- Short-circuit evaluation (return as soon as found)
- Preserve duplicate tracking (existing behavior)
- Return agent dict or `None`

**Tests**: 5 tests in `TestEnhancedFindAgent`

**Implementation Hint**:
```python
def _find_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
    """Find agent in session data, return latest entry.

    Multi-method detection (Issue #71):
    1. Check agent tracker (existing behavior)
    2. Analyze JSON structure (external modifications)
    3. Parse session text file (Task tool agents)

    Also tracks if there are duplicates for warning purposes.
    """
    # Priority 1: Check tracker (existing behavior - FAST)
    agents = [a for a in self.session_data.get("agents", []) if a["agent"] == agent_name]

    if agents:
        # Track duplicates (existing behavior)
        if len(agents) > 1 and not hasattr(self, '_duplicate_agents'):
            self._duplicate_agents = []
        if len(agents) > 1:
            self._duplicate_agents.append(agent_name)

        # Return latest entry
        return agents[-1]

    # Priority 2: Check JSON structure (external modifications)
    agent_data = self._detect_agent_from_json_structure(agent_name)
    if agent_data is not None:
        return agent_data

    # Priority 3: Parse session text (Task tool agents)
    session_text_file = self._get_session_text_file()
    if session_text_file is not None:
        agent_data = self._detect_agent_from_session_text(agent_name, session_text_file)
        if agent_data is not None:
            return agent_data

    # Not found in any method
    return None
```

---

## Testing Strategy

### After Each Method Implementation:

1. **Run Unit Tests**:
   ```bash
   # Test specific class
   python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestDataValidation -v
   python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestSessionTextParser -v
   python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestJSONStructureAnalyzer -v
   python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestEnhancedFindAgent -v
   ```

2. **Run Integration Tests**:
   ```bash
   python -m pytest tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v
   ```

3. **Run All Tests**:
   ```bash
   # Full test suite
   python -m pytest tests/unit/test_verify_parallel_exploration_task_tool.py tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v
   ```

### Check for Regressions:
```bash
# Run existing parallel exploration tests
python -m pytest tests/unit/test_parallel_exploration_logic.py -v
python -m pytest tests/unit/test_verify_parallel_validation_checkpoint.py -v
python -m pytest tests/integration/test_parallel_research_planning.py -v
python -m pytest tests/integration/test_parallel_validation.py -v
```

---

## Common Pitfalls

### 1. Path Traversal Security
**Problem**: Session text file path from user input → security risk

**Solution**: Always use `validate_path()` from `security_utils.py`
```python
from security_utils import validate_path
validate_path(session_text_path, allow_outside_project=False)
```

### 2. Corrupted JSON Handling
**Problem**: `json.loads()` can raise `JSONDecodeError`

**Solution**: Catch exception, return `None`
```python
try:
    session_data = json.loads(self.session_file.read_text())
except json.JSONDecodeError:
    return None  # Graceful degradation
```

### 3. Missing Session Text File
**Problem**: Not all sessions have .md files

**Solution**: Check existence before reading
```python
text_path = Path(session_text_path)
if not text_path.exists():
    return None
```

### 4. Invalid Timestamp Format
**Problem**: Timestamps might be malformed

**Solution**: Try parsing, catch `ValueError`
```python
try:
    datetime.fromisoformat(timestamp_str)
except (ValueError, TypeError):
    return False  # Invalid format
```

### 5. Duplicate Agent Tracking
**Problem**: Breaking existing duplicate tracking behavior

**Solution**: Preserve existing logic in `_find_agent()`
```python
if len(agents) > 1:
    if not hasattr(self, '_duplicate_agents'):
        self._duplicate_agents = []
    self._duplicate_agents.append(agent_name)
```

---

## Performance Benchmarks

### Must Meet:
- **Multi-method detection**: < 100ms (integration test)
- **Session text parsing**: < 50ms (integration test)
- **Short-circuit evaluation**: Tracker method should not call other methods (unit test)

### Optimization Tips:
1. **Short-circuit early**: Return as soon as agent found
2. **Lazy evaluation**: Don't compute session text path if not needed
3. **Regex compilation**: Compile regex patterns once if called frequently
4. **File I/O caching**: Consider caching session text content (future optimization)

---

## Security Checklist

- ✅ Path traversal prevention (use `validate_path()`)
- ✅ Symlink protection (validate_path resolves symlinks)
- ✅ No arbitrary code execution (JSON parsing only)
- ✅ Input validation (agent_name, timestamps)
- ✅ Audit logging (log all operations)
- ✅ Graceful error handling (no crashes on malformed data)

---

## Acceptance Criteria

### Must Pass:
1. ✅ All 33 tests pass (21 unit + 12 integration)
2. ✅ No regressions (existing tests still pass)
3. ✅ Performance benchmarks met (< 100ms, < 50ms)
4. ✅ Security tests pass (path traversal blocked)
5. ✅ Code coverage > 80% (run `pytest --cov`)

### Should Have:
1. ✅ Clear docstrings (Google style)
2. ✅ Type hints (all parameters and returns)
3. ✅ Error handling (graceful degradation)
4. ✅ Audit logging (all operations logged)
5. ✅ Code comments (explain complex regex, logic)

---

## Implementation Checklist

### Step 1: Helper Methods
- [ ] Implement `_validate_agent_data()`
- [ ] Run tests: `TestDataValidation` (4 tests)
- [ ] Verify all pass

- [ ] Implement `_get_session_text_file()`
- [ ] Run integration tests to verify
- [ ] Verify no errors

### Step 2: Detection Methods
- [ ] Implement `_detect_agent_from_session_text()`
- [ ] Run tests: `TestSessionTextParser` (5 tests)
- [ ] Verify all pass

- [ ] Implement `_detect_agent_from_json_structure()`
- [ ] Run tests: `TestJSONStructureAnalyzer` (4 tests)
- [ ] Verify all pass

### Step 3: Integration
- [ ] Enhance `_find_agent()` with multi-method detection
- [ ] Run tests: `TestEnhancedFindAgent` (5 tests)
- [ ] Verify all pass

### Step 4: End-to-End Testing
- [ ] Run all unit tests (21 tests)
- [ ] Run all integration tests (12 tests)
- [ ] Verify all 33 tests pass

### Step 5: Regression Testing
- [ ] Run existing parallel exploration tests
- [ ] Run existing parallel validation tests
- [ ] Verify no regressions

### Step 6: Performance & Security
- [ ] Run performance validation tests
- [ ] Run security validation tests
- [ ] Verify benchmarks met

### Step 7: Finalization
- [ ] Add docstrings to all new methods
- [ ] Add type hints
- [ ] Add audit logging
- [ ] Code review (self-review against checklist)

---

## Estimated Time

- **Helper Methods**: 30 minutes
- **Detection Methods**: 1.5 hours
- **Integration**: 30 minutes
- **Testing & Debugging**: 1 hour
- **Documentation & Review**: 30 minutes

**Total**: ~4 hours

---

## Success Signals

### You Know You're Done When:
1. ✅ All 33 tests pass (100% green)
2. ✅ No regressions (existing tests still pass)
3. ✅ Performance benchmarks met
4. ✅ Security tests pass
5. ✅ Code coverage report shows > 80%
6. ✅ No TODO comments in code
7. ✅ All methods have docstrings
8. ✅ All methods have type hints
9. ✅ Audit logging in place
10. ✅ Self-review complete

---

## Need Help?

### Debugging Tips:
1. **Run single test**: `pytest tests/unit/test_verify_parallel_exploration_task_tool.py::TestSessionTextParser::test_valid_completion_marker_returns_agent_data -v`
2. **Add print statements**: Debug what's being parsed
3. **Check regex**: Use regex101.com to test patterns
4. **Validate paths**: Print resolved paths to verify security
5. **Check test fixtures**: Understand test data structure

### Reference Implementation:
- **Existing `_find_agent()`**: See line ~1200 in `agent_tracker.py`
- **Existing timestamp validation**: See `_validate_timestamps()` method
- **Security validation**: See `security_utils.py` for `validate_path()` usage
- **Audit logging**: See any existing method for audit_log() pattern

---

## Questions?

Contact test-master agent or refer to:
- Test files: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/test_verify_parallel_exploration_task_tool.py`
- Integration tests: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_parallel_exploration_task_tool_end_to_end.py`
- TDD Red Complete doc: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_71_TDD_RED_COMPLETE.md`
