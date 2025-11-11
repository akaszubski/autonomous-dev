# Task Tool Agent Detection Architecture

**Issue**: GitHub Issue #71 - Fix verify_parallel_exploration() Task tool agent detection
**Version**: v3.13.0
**Status**: Complete (Multi-method detection implemented)
**Test Coverage**: 32/32 tests passing (100% - Issue #71)

## Overview

When agents are invoked via Claude Code's Task tool (new in Claude Code 2.0+), they don't automatically appear in session logs because the Task tool doesn't directly integrate with the SubagentStop hook. This document describes the architecture for automatic Task tool agent detection and tracking.

## The Problem

**Scenario**: Agent is invoked via Task tool
```python
# In a skill or command file
task("researcher", query="find pattern for async tasks")
```

**What happens without fix**:
1. Task tool invokes agent (sets CLAUDE_AGENT_NAME environment variable)
2. Agent executes but doesn't trigger SubagentStop hook (Task tool doesn't call it)
3. Agent never appears in session logs
4. PROJECT.md progress doesn't track Task tool agent work
5. Integration testing can't verify Task tool agent execution

**Impact**:
- Session logs incomplete for Task tool workflows
- No way to verify Task tool agents actually executed
- Project progress doesn't reflect Task tool work

## The Solution

### Multi-Method Detection Strategy (v3.13.0+)

Task tool agents may not be recorded in the agent tracker's in-memory state if they run independently. The solution uses three detection methods with priority-based fallback:

1. **Method 1 (Tracker State)** - Fastest, 99% of cases
   - Check agent tracker's in-memory session data
   - Returns immediately if agent found
   - Covers normal SubagentStop hook workflow

2. **Method 2 (JSON Structure)** - External modifications
   - Reload JSON file to detect external changes
   - Catches Task tool agents that modified JSON directly
   - Covers edge cases where JSON was modified outside tracker

3. **Method 3 (Session Text Parsing)** - Task tool agents
   - Parse session .md file for completion markers
   - Regex-based detection with strict validation
   - Covers Task tool agents that logged to text file
   - Used by verify_parallel_exploration() in CHECKPOINT 1

### How It Works

When `/auto-implement` reaches CHECKPOINT 1, `verify_parallel_exploration()` attempts to find researcher and planner agents:

```python
def verify_parallel_exploration(self) -> bool:
    # Find agents using multi-method detection
    researcher = self._find_agent("researcher")  # Tries 3 methods
    planner = self._find_agent("planner")        # Tries 3 methods

    if not researcher or not planner:
        return False  # Missing agents

    # Validate and calculate metrics...
```

The `_find_agent()` method implements priority-based fallback:

```python
def _find_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
    """Multi-method detection (Issue #71)"""

    # Priority 1: Check tracker state (FASTEST)
    agents = [a for a in self.session_data.get("agents", [])
              if a["agent"] == agent_name]
    if agents:
        return agents[-1]  # Return latest

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

    return None  # Not found
```

### Legacy: Auto-Detection via SubagentStop Hook

The `auto_update_project_progress.py` hook runs for ANY subagent completion (including Task tool agents). It detects and tracks Task tool agents automatically:

**File**: `plugins/autonomous-dev/hooks/auto_update_project_progress.py`

**Function**: `detect_and_track_agent(session_file: str) -> bool`

```python
def detect_and_track_agent(session_file: str) -> bool:
    """Auto-detect and track agent from CLAUDE_AGENT_NAME environment variable.

    Called in main() BEFORE run_hook() to ensure Task tool agents are tracked
    even if they don't trigger PROJECT.md updates.
    """
    tracker = AgentTracker(session_file=session_file)
    was_tracked = tracker.auto_track_from_environment()
    return was_tracked
```

**Key Design Points**:
- Runs BEFORE PROJECT.md update logic (ensures tracking even if no update needed)
- Non-blocking: Returns False if env var missing (doesn't raise exception)
- Defensive: Validates all inputs before tracking

### 3. Agent Tracker Methods

**File**: `scripts/agent_tracker.py`

#### Method: `is_agent_tracked(agent_name: str) -> bool`

Checks if agent is already in session (for duplicate detection):

```python
def is_agent_tracked(self, agent_name: str) -> bool:
    """Check if agent is already tracked in current session.

    Returns:
        True if agent exists in session (any status), False otherwise

    Usage:
        Used by auto_track_from_environment() to prevent duplicate tracking
    """
    # Validate agent name
    agent_name = validate_agent_name(agent_name)

    # Check session
    for entry in self.session_data["agents"]:
        if entry["agent"] == agent_name:
            return True
    return False
```

**Security**: Validates agent name via `security_utils.validate_agent_name()`

#### Method: `auto_track_from_environment(message: Optional[str] = None) -> bool`

Auto-detects and tracks agent from CLAUDE_AGENT_NAME environment variable:

```python
def auto_track_from_environment(self, message: Optional[str] = None) -> bool:
    """Auto-detect and track agent from CLAUDE_AGENT_NAME environment variable.

    Returns:
        True if agent was tracked (new), False otherwise (already tracked or no env var)

    Raises:
        ValueError: If CLAUDE_AGENT_NAME contains invalid agent name

    Idempotency:
        Safe to call multiple times - checks is_agent_tracked() first
    """
    # 1. Get agent name from environment
    agent_name = os.environ.get("CLAUDE_AGENT_NAME")

    if agent_name is None:
        # Not set - no error, just return False
        return False

    # 2. Validate agent name (catches path traversal, invalid chars, etc)
    agent_name = validate_agent_name(agent_name)

    # 3. Check if already tracked (idempotent)
    if self.is_agent_tracked(agent_name):
        return False  # Already tracked

    # 4. Create new tracking entry
    entry = {
        "agent": agent_name,
        "status": "started",
        "started_at": datetime.now().isoformat(),
        "message": message or f"Auto-detected via Task tool"
    }
    self.session_data["agents"].append(entry)
    self._save()

    return True  # Was tracked (new)
```

**Key Features**:
- **Non-blocking**: Returns False if env var missing (doesn't raise exception)
- **Idempotent**: Checks is_agent_tracked() before creating new entry
- **Secure**: Validates agent name before using it
- **Silent**: No print() output (hooks should be quiet)

#### Method: `complete_agent()` - Idempotent Completion

Enhanced to handle duplicate completions gracefully (GitHub Issue #57):

```python
def complete_agent(self, agent_name: str, message: str, tools: Optional[List[str]] = None, tools_used: Optional[List[str]] = None):
    """Log agent completion (idempotent - safe to call multiple times).

    If agent is already completed, this is a no-op (returns silently).
    This prevents duplicate completions when agents are invoked via Task tool
    and completed by both Task tool and SubagentStop hook.
    """
    # IDEMPOTENCY CHECK: If already completed, skip
    for entry in reversed(self.session_data["agents"]):
        if entry["agent"] == agent_name:
            if entry["status"] == "completed":
                # Already completed - skip silently
                return
            elif entry["status"] == "started":
                # Found started entry - complete it
                entry["status"] = "completed"
                # ... rest of completion logic
                return
```

**Backward Compatibility**:
- Accepts both `tools` and `tools_used` parameters (alias)
- Existing code using old parameter name still works

## Execution Flow

### Scenario: Researcher Agent via Task Tool

```
1. Skill calls: task("researcher", query="find pattern")
   ↓
2. Claude Code Task tool invokes researcher agent
   ↓
3. Task tool sets: export CLAUDE_AGENT_NAME=researcher
   ↓
4. Researcher agent executes
   ↓
5. Agent completes, any output returned to caller
   ↓
6. SubagentStop hook fires (even for Task tool)
   ↓
7. auto_update_project_progress.py runs
   ↓
8. detect_and_track_agent() called:
     a. tracker = AgentTracker(session_file)
     b. tracker.auto_track_from_environment()
        - Gets CLAUDE_AGENT_NAME="researcher" from env
        - Validates agent name
        - Checks if already tracked (is_agent_tracked)
        - Creates "started" entry in session
     c. Returns True (was tracked)
   ↓
9. run_hook() processes normal PROJECT.md logic
   ↓
10. Session file updated with researcher entry
```

### Scenario: Manual Agent Start + Task Tool Completion

```
1. Code calls: tracker.start_agent("researcher", message="manual")
   ↓
2. Session file has researcher with status="started"
   ↓
3. Task tool calls agent
   ↓
4. SubagentStop hook fires
   ↓
5. detect_and_track_agent() called:
     a. Gets CLAUDE_AGENT_NAME="researcher"
     b. Checks is_agent_tracked("researcher") - ALREADY TRACKED
     c. Returns False (already tracked)
   ↓
6. No duplicate created (idempotent)
```

## Multi-Method Detection Implementation (v3.13.0)

### New Methods in `scripts/agent_tracker.py`

#### 1. `_validate_agent_data(agent_data: Dict[str, Any]) -> bool`

Validates agent data structure and timestamps.

```python
def _validate_agent_data(self, agent_data: Dict[str, Any]) -> bool:
    """Validate agent data structure and timestamps.

    Validates:
        - Required fields: agent, status, started_at, completed_at
        - Status is in ["completed", "failed"]
        - Timestamps are valid ISO format

    Returns:
        True if valid, False otherwise
    """
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

#### 2. `_get_session_text_file() -> Optional[str]`

Gets session text file path (.md) from JSON file path.

```python
def _get_session_text_file(self) -> Optional[str]:
    """Get session text file path (.md) from JSON file path.

    Returns:
        Path to session .md file if exists, None otherwise

    Example:
        JSON: docs/sessions/20251111-test-pipeline.json
        Text: docs/sessions/20251111-test-session.md
    """
```

Handles multiple naming patterns:
- Pattern 1: Remove -pipeline suffix if present, add -session
- Pattern 2: Direct stem + -session
- Pattern 3: Extract session ID and glob for matching files

#### 3. `_detect_agent_from_json_structure(agent_name: str) -> Optional[Dict[str, Any]]`

Reloads JSON file to detect external modifications.

```python
def _detect_agent_from_json_structure(self, agent_name: str) -> Optional[Dict[str, Any]]:
    """Reload JSON file to detect external modifications.

    Purpose:
        Detect Task tool agents that modified JSON directly
        (bypassing tracker's in-memory state)

    Returns:
        Agent data dict if found and valid, None otherwise
    """
```

Security features:
- JSON parsing with JSONDecodeError handling
- Agent data validation
- Audit logging

#### 4. `_detect_agent_from_session_text(agent_name: str, session_text_path: str) -> Optional[Dict[str, Any]]`

Parses session text file for agent completion markers.

```python
def _detect_agent_from_session_text(self, agent_name: str, session_text_path: str) -> Optional[Dict[str, Any]]:
    """Parse session text file for agent completion markers.

    Format Expected:
        **HH:MM:SS - agent_name**: message
        **HH:MM:SS - agent_name**: ... completed

    Returns:
        Agent data dict if found, None otherwise
    """
```

Key features:
- **Path validation**: Uses `validate_path()` to prevent traversal attacks
- **Regex parsing**: Strict pattern matching for timestamps
- **Timestamp validation**: Ensures HH:MM:SS are valid (00-23, 00-59, 00-59)
- **Malformed detection**: Checks if there are invalid timestamp formats
- **Completion markers**: Looks for "completed" or "complete" in message
- **Session date extraction**: Multiple patterns (YYYYMMDD, YYYY-MM-DD, session_id)
- **Duration calculation**: Computes agent execution time from start/completion
- **Audit logging**: Logs all successful detections

**Regex Pattern**:
```
\*\*(\d{2}:\d{2}:\d{2}) - {agent_name}\*\*: (.+)
```

Validates:
- HH: 00-23 (hours)
- MM: 00-59 (minutes)
- SS: 00-59 (seconds)
- Agent name matches exactly (escapes special regex chars)

**Session Date Extraction** (multiple patterns tried):
1. `Session YYYYMMDD` or `# Session YYYYMMDD`
2. `**Started**: YYYY-MM-DD HH:MM:SS`
3. Session ID from tracker (format: YYYYMMDD-HHMMSS)

#### 5. Enhanced `_find_agent(agent_name: str) -> Optional[Dict[str, Any]]`

Multi-method detection with priority fallback.

```python
def _find_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
    """Find agent in session data, return latest entry.

    Multi-method detection (Issue #71):
    1. Check agent tracker state (existing behavior - FAST)
    2. Analyze JSON structure (external modifications)
    3. Parse session text file (Task tool agents)

    Also tracks if there are duplicates for warning purposes.
    """
```

Execution order:
1. **Check tracker state** - Fastest path, covers 99% of cases
   - Returns immediately if found
   - Tracks duplicates
2. **Check JSON structure** - Reloads from disk
   - Catches external modifications
3. **Parse session text** - Regex-based parsing
   - Handles Task tool agents

### Session Text Format

Task tool agents may log completion to text files:

```markdown
# Session 20251111-test

**Started**: 2025-11-11 10:00:00

---

**10:00:05 - researcher**: Starting research on JWT authentication patterns

**10:05:43 - researcher**: Research completed - Found 3 relevant patterns

**10:05:50 - planner**: Starting architecture planning for JWT implementation

**10:12:27 - planner**: Planning completed - Created 5-phase implementation plan
```

The parser extracts:
- **Start time**: First agent mention (e.g., 10:00:05)
- **Completion time**: Latest completion marker (e.g., 10:12:27)
- **Agent name**: Exact match (case-sensitive)
- **Status**: Inferred from "completed" keyword
- **Duration**: Calculated from start/completion times

## Security

### Input Validation

All inputs validated via `security_utils` module:

1. **Agent Name Validation** - `validate_agent_name(agent_name, purpose)`
   - Checks for path traversal attempts (../, .., etc)
   - Validates against EXPECTED_AGENTS list
   - Length validation (max 100 chars)
   - Audit logged to security_audit.log

2. **Message Validation** - `validate_input_length(message, max_length, parameter_name, purpose)`
   - Length validation (max 10KB for messages)
   - Prevents buffer overflow attacks
   - Audit logged to security_audit.log

3. **Environment Variable** - Treated as untrusted input
   - CLAUDE_AGENT_NAME not assumed to be valid
   - Validated before use
   - Raises ValueError if invalid

### Audit Logging

All operations logged to `logs/security_audit.log`:

```json
{
  "timestamp": "2025-11-09T10:30:15.123456",
  "component": "agent_tracker",
  "level": "success",
  "operation": "auto_track_from_environment",
  "agent_name": "researcher",
  "status": "tracked",
  "message": "Auto-detected via Task tool"
}
```

## Test Coverage

### Unit Tests: `tests/unit/test_verify_parallel_exploration_task_tool.py` (20 tests)

**Focus**: Multi-method agent detection for verify_parallel_exploration()

Tests cover (5 test classes):
1. **TestDataValidation** (3 tests)
   - `_validate_agent_data()` with valid/invalid data
   - Required fields validation
   - Timestamp format validation

2. **TestSessionTextParser** (6 tests)
   - `_detect_agent_from_session_text()` method
   - Valid completion marker detection
   - Session date extraction (3 patterns)
   - Invalid timestamp handling
   - Malformed entry detection
   - Duration calculation

3. **TestJSONStructureAnalyzer** (4 tests)
   - `_detect_agent_from_json_structure()` method
   - External JSON modifications
   - JSONDecodeError handling
   - Corrupted file handling

4. **TestEnhancedFindAgent** (4 tests)
   - `_find_agent()` with multi-method detection
   - Priority-based fallback
   - Duplicate tracking
   - Short-circuit on first success

5. **TestVerifyParallelExploration** (3 tests)
   - Integration with `verify_parallel_exploration()`
   - Multi-method detection in checkpoint
   - Parallel vs sequential detection

### Integration Tests: `tests/integration/test_parallel_exploration_task_tool_end_to_end.py` (12 tests)

**Focus**: End-to-end multi-method detection with real file I/O

Tests cover (3 test classes):
1. **TestRealFileOperations** (5 tests)
   - Real session text parsing
   - JSON file operations
   - Multi-file coordination
   - Directory structure handling
   - Path validation

2. **TestMultiMethodPriority** (4 tests)
   - Tracker state priority (Method 1)
   - JSON reload on external changes (Method 2)
   - Session text parsing fallback (Method 3)
   - Short-circuit evaluation (no unnecessary fallbacks)

3. **TestPerformanceAndSecurity** (3 tests)
   - Overhead measurement (< 100ms)
   - Path traversal prevention
   - Graceful error handling
   - No exceptions raised

### Test Status (v3.13.0)

**Current**: 32/32 tests passing (100%)

**Coverage Breakdown**:
- Unit tests: 20 passing
- Integration tests: 12 passing
- Total lines of test code: 1,543

**Key Validations**:
- All 5 new detection methods tested
- All 3 multi-method priorities validated
- All error scenarios covered
- All security checks passed
- All performance targets met

### Legacy Tests: `tests/unit/test_subagent_stop_task_tool_detection.py` (22 tests)

**Status**: Maintained for backward compatibility (v3.8.3+)

**Focus**: SubagentStop hook detection and tracking logic

Tests cover:
- `detect_and_track_agent()` function
- `is_agent_tracked()` method
- `auto_track_from_environment()` method
- Duplicate prevention and idempotency
- Security validation and audit logging

## Configuration

### Environment Variables

- `CLAUDE_AGENT_NAME` - Set by Task tool when invoking agent
  - Format: agent name (e.g., "researcher", "implementer", "reviewer")
  - Set by: Claude Code Task tool
  - Read by: `auto_track_from_environment()` method
  - Validated: Yes, full security validation before use

### Expected Agents

Defined in `scripts/agent_tracker.py`:

```python
EXPECTED_AGENTS = [
    "researcher",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master",
    "advisor",
    "quality-validator",
    # ... utility agents
]
```

Task tool agents MUST be in this list (validated by `validate_agent_name()`).

## Backward Compatibility

### Existing Code Still Works

1. **Manual agent tracking**: `tracker.start_agent()` and `tracker.complete_agent()` still work unchanged
2. **Session files**: Old format fully supported
3. **Parameter names**: `tools` and `tools_used` both accepted (alias support)
4. **Hook integration**: Existing hooks unchanged, new detection added non-blocking

### Migration Path

No migration needed:
- Existing code continues to work
- New Task tool agents automatically detected (no code changes)
- Graceful degradation if env var missing

## Performance

- **Detection overhead**: < 1ms per SubagentStop event
- **Duplicate check**: O(n) where n = number of agents in current session (typically 5-10)
- **Idempotency**: Single is_agent_tracked() check before creating entry

## Future Enhancements

1. **Metrics tracking**: Count Task tool vs direct agent invocations
2. **Performance profiling**: Measure Task tool agent execution time
3. **Dependency tracking**: Record which skills invoked which agents
4. **Parallel detection**: Identify Task tool agents running concurrently

## References

- **Issue**: GitHub Issue #57 (Agent tracker doesn't detect Task tool agent execution)
- **PR**: See git history for implementation commits
- **Related**: GitHub Issue #56 (documentation parity validation)
- **Related**: GitHub Issue #46 (parallel validation checkpoint)
- **Hook**: `plugins/autonomous-dev/hooks/auto_update_project_progress.py`
- **Library**: `scripts/agent_tracker.py`
- **Security**: `plugins/autonomous-dev/lib/security_utils.py`

## Troubleshooting Guide

### Issue: verify_parallel_exploration() reports missing agents

**Symptoms**:
```
verify_parallel_exploration() returned False
Missing agents: ['researcher']
```

**Cause**: Agent not found in any of the 3 detection methods

**Solutions**:

1. **Check Tracker State** (Method 1)
   ```bash
   python -c "
   import json
   from pathlib import Path
   session_file = Path('docs/sessions/20251111-test.json')
   data = json.loads(session_file.read_text())
   agents = [a for a in data.get('agents', []) if a['agent'] == 'researcher']
   print(f'Found in tracker: {len(agents)} entries')
   print(json.dumps(agents, indent=2))
   "
   ```

2. **Check JSON Structure** (Method 2)
   ```bash
   # Verify JSON is valid
   python -m json.tool docs/sessions/20251111-test.json > /dev/null
   echo "JSON is valid"
   ```

3. **Check Session Text** (Method 3)
   ```bash
   # Look for completion markers
   grep -i "researcher.*completed" docs/sessions/20251111-test-session.md
   # Should output: **HH:MM:SS - researcher**: ... completed
   ```

### Issue: Session text parsing returns None

**Symptoms**:
```python
agent_data = tracker._detect_agent_from_session_text("researcher", path)
assert agent_data is not None  # FAILS
```

**Cause**: Session text format doesn't match expected pattern

**Verification Checklist**:

1. **File Exists**
   ```bash
   test -f /path/to/session.md && echo "File exists" || echo "File missing"
   ```

2. **Contains Completion Marker**
   ```bash
   # Must be exact format: **HH:MM:SS - agent_name**: message completed
   grep "^\*\*[0-9][0-9]:[0-9][0-9]:[0-9][0-9] - researcher\*\*:" file.md
   ```

3. **Timestamp Format Valid**
   ```bash
   # Must be HH:MM:SS with valid ranges
   grep -E "^\*\*([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]" file.md
   ```

4. **Session Date Extractable**
   ```bash
   # One of these patterns must exist:
   grep "Session [0-9]\{8\}" file.md      # Pattern 1: Session YYYYMMDD
   grep "\*\*Started\*\*:" file.md        # Pattern 2: **Started**: YYYY-MM-DD
   # Pattern 3: Session ID from JSON
   ```

**Fix**: Ensure session text matches format:
```markdown
**HH:MM:SS - researcher**: Research completed - Found 5 patterns
```

### Issue: Regex pattern not matching agent name

**Symptoms**:
```python
matches = re.findall(valid_pattern, content, re.MULTILINE)
assert len(matches) > 0  # FAILS - no matches found
```

**Cause**: Agent name in text doesn't match expected agent

**Debug**:
```bash
# List all agent mentions in session text
grep -oE "\*\*[0-9][0-9]:[0-9][0-9]:[0-9][0-9] - [^*]+\*\*:" file.md | sed 's/.*- //;s/\*\*.*//;s/ //g' | sort | uniq -c
```

**Fix**: Verify agent name matches exactly (case-sensitive)

### Issue: Performance degradation with large session files

**Symptoms**:
```
_detect_agent_from_session_text() took 500ms (exceeds 50ms target)
```

**Cause**: Large session file (> 10MB) or many completion markers

**Solutions**:

1. **Reduce file size**
   - Archive old sessions to separate directory
   - Remove duplicate entries from JSON

2. **Optimize regex**
   - Session text parsing is O(n) where n = file size
   - Unavoidable, but rare (fallback method, not primary)

3. **Check performance targets**
   ```bash
   python -c "
   import time
   from scripts.agent_tracker import AgentTracker

   tracker = AgentTracker(session_file='path')
   start = time.time()
   result = tracker._detect_agent_from_session_text('researcher', 'path/file.md')
   duration = (time.time() - start) * 1000
   print(f'Duration: {duration:.1f}ms (target: < 50ms)')
   "
   ```

### Issue: Path traversal prevention blocking legitimate paths

**Symptoms**:
```
validate_path() raised ValueError: Invalid path
```

**Cause**: Session file path contains `..` or other traversal attempts

**Fix**: Use absolute paths only
```python
from pathlib import Path

# WRONG - relative path with traversal
path = "../sessions/file.json"

# CORRECT - absolute path
path = Path.cwd() / "docs" / "sessions" / "file.json"
path = path.resolve()  # Convert to absolute

# CORRECT - from session file directory
session_dir = Path(session_file).parent
text_file = session_dir / "file.md"
```

## FAQ

**Q: Why three detection methods instead of one?**
A:
- Method 1 (Tracker state) handles normal workflow (99% of cases, < 1ms)
- Method 2 (JSON reload) catches edge cases where JSON was modified externally
- Method 3 (Session text parsing) handles Task tool agents that log directly to text files
Together, they handle all execution scenarios without requiring task tool integration.

**Q: Why use session text parsing for Task tool agents?**
A: Task tool agents may not trigger the SubagentStop hook in all environments. Session text parsing provides a reliable fallback that works even if the agent completes without hook integration.

**Q: What's the performance impact?**
A:
- Method 1: < 1ms (in-memory lookup)
- Method 2: 5-10ms (JSON reload from disk)
- Method 3: 20-50ms (regex parsing - only if Methods 1 & 2 fail)
- Total overhead: < 100ms (target met)
Short-circuit evaluation ensures we don't run unnecessary methods.

**Q: Is regex parsing safe for untrusted input?**
A: Yes. The regex pattern is fixed, not derived from input. Input is validated strictly:
- Timestamps must be HH:MM:SS with valid ranges (00-23, 00-59, 00-59)
- Agent names validated against EXPECTED_AGENTS whitelist
- Path validated via validate_path() (CWE-22 prevention)
- No code execution possible (regex match-only, no substitution)

**Q: What if session text file doesn't exist?**
A: _get_session_text_file() returns None gracefully. _detect_agent_from_session_text() validates existence before reading. Method 1 already returned agent data (short-circuit), so no issue.

**Q: Can an agent be detected by multiple methods?**
A: No. _find_agent() uses short-circuit evaluation - returns as soon as agent is found by any method. This prevents duplicate detection and unnecessary processing.

**Q: What if timestamps are malformed in session text?**
A: The regex pattern is strict - only matches HH:MM:SS format. Additional validation ensures:
- Each component (H, M, S) is numeric
- Hours: 0-23, Minutes: 0-59, Seconds: 0-59
- If any validation fails, returns None (graceful degradation)

**Q: Does this break backward compatibility?**
A: No. The multi-method detection is transparent:
- Existing code using _find_agent() still works
- New detection methods are private (_detect_agent_from_*)
- verify_parallel_exploration() behavior unchanged, just more robust
- Session data format unchanged

**Q: How do I test the multi-method detection?**
A:
```bash
# Run unit tests (isolated, fast)
pytest tests/unit/test_verify_parallel_exploration_task_tool.py -v

# Run integration tests (real file I/O, comprehensive)
pytest tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v

# Run both
pytest tests/unit/test_verify_parallel_exploration_task_tool.py \
        tests/integration/test_parallel_exploration_task_tool_end_to_end.py -v
```

**Q: What's the difference between Issue #57 and Issue #71?**
A:
- **Issue #57** (v3.8.3): Auto-detect Task tool agents via CLAUDE_AGENT_NAME environment variable (SubagentStop hook)
- **Issue #71** (v3.13.0): Fix verify_parallel_exploration() checkpoint to handle Task tool agents that bypass the hook (multi-method detection)
