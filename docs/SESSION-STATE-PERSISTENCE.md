# Session State Persistence

Persistent session state management for autonomous-dev workflows. Session state survives `/clear` operations and enables cross-session context preservation.

**Location**: `.claude/local/SESSION_STATE.json` (protected by `.claude/local/**` pattern during `/sync`)

**Issue**: #247

**Version**: v1.0.0

---

## Overview

SessionStateManager stores persistent session context that survives `/clear` operations. This enables workflows to track:

- **Session Context**: Coding conventions, active tasks, important files, repo-specific knowledge
- **Workflow State**: Last `/implement` completion, pending todos, recently modified files
- **Cross-Session Memory**: Session information persists across context clears

### Why Session State Matters

The `/clear` command wipes chat context to prevent token bloat, but development workflows often benefit from institutional memory:

- Coding conventions (naming patterns, architecture decisions)
- Active tasks and blockers
- Important files and their purposes
- Repo-specific knowledge (dependencies, build system, test patterns)

Session state enables agents to access this context without cluttering the conversation.

---

## Architecture

### State File Location

```
.claude/local/SESSION_STATE.json
```

**Protection**: Files in `.claude/local/**` are protected during `/sync` operations (never overwritten or deleted). This ensures session state persists across plugin updates.

### State Schema

```json
{
  "schema_version": "1.0",
  "last_updated": "2026-01-19T12:00:00Z",
  "last_session_id": "20260119-120000",
  "session_context": {
    "key_conventions": [
      "Use snake_case for functions",
      "Docstrings on all public methods"
    ],
    "active_tasks": [
      "Implement user authentication",
      "Add test coverage for payments module"
    ],
    "important_files": {
      "lib/auth.py": "Authentication logic and token validation",
      "tests/test_payments.py": "Payment integration tests"
    },
    "repo_specific": {
      "test_runner": "pytest",
      "python_version": "3.11+",
      "key_dependencies": ["FastAPI", "SQLAlchemy"]
    }
  },
  "workflow_state": {
    "last_implement": {
      "feature": "Add user authentication",
      "completed_at": "2026-01-19T11:45:00Z",
      "agents_completed": ["researcher", "planner", "implementer", "reviewer"]
    },
    "pending_todos": [
      "Add integration tests for OAuth",
      "Update API documentation"
    ],
    "recent_files": [
      "plugins/auth/lib/token_manager.py",
      "tests/integration/test_oauth.py",
      "docs/AUTHENTICATION.md"
    ]
  }
}
```

### Key Features

**1. Atomic Writes**: Uses temp file + rename pattern to prevent corruption on system crash

```python
# All writes are atomic (temp file → rename)
manager.save_state(state)  # Safe even if system crashes mid-write
```

**2. Thread Safety**: Reentrant locks for concurrent access

```python
# Multiple threads can safely update state
with lock:
    state = manager.load_state()
    manager.update_context(key_conventions=["..."])
    manager.save_state(state)
```

**3. Security**: Path traversal (CWE-22) and symlink (CWE-59) validation

```python
# Invalid paths rejected at init time
manager = SessionStateManager("../../../etc/passwd")  # Raises StateError
```

**4. Graceful Degradation**: Corrupted JSON returns default schema

```python
# If SESSION_STATE.json is corrupted:
state = manager.load_state()  # Returns default schema, not error
```

**5. Permission Control**: File mode 0o600 (owner read/write only)

```bash
ls -la .claude/local/SESSION_STATE.json
# -rw------- (0o600) owned by user
```

---

## API Reference

### SessionStateManager

Main class for session state management. Inherits from `StateManager[Dict[str, Any]]` ABC.

#### Constructor

```python
from session_state_manager import SessionStateManager

# Use default location (.claude/local/SESSION_STATE.json)
manager = SessionStateManager()

# Use custom location
manager = SessionStateManager(state_file="/path/to/custom/state.json")
```

**Parameters**:
- `state_file` (Optional[Path | str]): Custom state file path. If None, uses `.claude/local/SESSION_STATE.json` relative to project root.

**Raises**:
- `StateError`: If state_file contains path traversal (`..`) or symlink

#### load_state()

Load session state from file.

```python
state = manager.load_state()

print(state["session_context"]["key_conventions"])
# Output: ["Use snake_case for functions", ...]

print(state["workflow_state"]["last_implement"]["feature"])
# Output: "Add user authentication"
```

**Returns**: Session state dict

**Behavior**:
- Returns default schema if file doesn't exist
- Returns default schema if JSON is corrupted (graceful degradation)
- Validates path security (CWE-22, CWE-59)
- Merges loaded state with default schema (ensures all fields exist)

#### save_state()

Save session state to file (atomic write).

```python
state = manager.load_state()
state["session_context"]["key_conventions"].append("Always use type hints")
manager.save_state(state)
```

**Parameters**:
- `state` (Dict[str, Any]): State to persist

**Raises**:
- `StateError`: If write fails (permission error, disk full, etc.)

**Behavior**:
- Updates `last_updated` timestamp automatically
- Uses atomic write (temp file + rename)
- Sets file permissions to 0o600
- Thread-safe with file locking
- Audit logging on success and error

#### cleanup_state()

Remove session state file.

```python
manager.cleanup_state()  # Deletes .claude/local/SESSION_STATE.json
```

**Raises**:
- `StateError`: If cleanup fails

#### update_context()

Update session context (key_conventions, active_tasks, etc.).

```python
manager.update_context(
    key_conventions=[
        "Use snake_case for functions",
        "Docstrings on all public methods"
    ],
    active_tasks=[
        "Implement user authentication",
        "Add test coverage"
    ],
    important_files={
        "lib/auth.py": "Authentication logic",
        "tests/test_auth.py": "Auth tests"
    },
    repo_specific={
        "test_runner": "pytest",
        "python_version": "3.11+"
    }
)
```

**Parameters**:
- `key_conventions` (Optional[List[str]]): Coding conventions to add
- `active_tasks` (Optional[List[str]]): Tasks to add
- `important_files` (Optional[Dict[str, str]]): Files with descriptions
- `repo_specific` (Optional[Dict[str, Any]]): Repo-specific metadata

**Behavior**:
- Merges with existing data (additive, no overwrite)
- Automatically deduplicates key_conventions and active_tasks
- Loads state, updates, then saves (atomic operation)

#### record_implement_completion()

Record `/implement` workflow completion.

```python
manager.record_implement_completion(
    feature="Add user authentication",
    agents_completed=["researcher", "planner", "implementer", "reviewer"],
    files_modified=["lib/auth.py", "tests/test_auth.py"]
)
```

**Parameters**:
- `feature` (str): Feature description
- `agents_completed` (List[str]): Agents that completed
- `files_modified` (Optional[List[str]]): Files modified by implementation

**Behavior**:
- Updates `workflow_state.last_implement` with timestamp
- Adds modified files to `recent_files` (deduplicates)
- Preserves pending_todos and other workflow state
- Automatically saves state

#### get_session_summary()

Get human-readable session state summary.

```python
summary = manager.get_session_summary()
print(summary)

# Output:
# SESSION STATE SUMMARY
# ============================================================
# Last Updated: 2026-01-19T12:00:00Z
# Session ID: 20260119-120000
#
# SESSION CONTEXT:
#   Conventions: 2
#     - Use snake_case for functions
#     - Docstrings on all public methods
#   Active Tasks: 2
#     - Implement user authentication
#     - Add test coverage for payments module
#   Important Files: 2
#     - lib/auth.py: Authentication logic and token validation
#     - tests/test_payments.py: Payment integration tests
#
# WORKFLOW STATE:
#   Last /implement: Add user authentication
#     Completed: 2026-01-19T11:45:00Z
#     Agents: researcher, planner, implementer, reviewer
#   Recent Files: 2
#     - plugins/auth/lib/token_manager.py
#     - tests/integration/test_oauth.py
# ============================================================
```

**Returns**: Formatted summary string

**Behavior**:
- Shows first 5 items in each category with "... and N more" for overflow
- Loads current state from file
- Safe to call multiple times (no side effects)

---

## Usage Examples

### Example 1: Initialize Session Context After Project Bootstrap

```python
from session_state_manager import SessionStateManager

# Initialize manager
manager = SessionStateManager()

# Record project conventions discovered during setup
manager.update_context(
    key_conventions=[
        "Use snake_case for variables and functions",
        "All public methods must have docstrings",
        "Type hints required for function parameters",
        "90% test coverage minimum for new code"
    ],
    repo_specific={
        "test_framework": "pytest",
        "python_version": "3.11+",
        "main_branch": "master",
        "ci_system": "GitHub Actions",
        "key_dependencies": ["FastAPI", "SQLAlchemy", "pytest"]
    }
)

print("Session context initialized")
```

### Example 2: Track Active Tasks

```python
manager = SessionStateManager()

# Add active tasks
manager.update_context(
    active_tasks=[
        "Implement user authentication system",
        "Add OAuth2 support",
        "Set up integration tests for payments module"
    ]
)

# Later, after completing a task
state = manager.load_state()
state["session_context"]["active_tasks"] = [
    "Add OAuth2 support",
    "Set up integration tests for payments module"
]
manager.save_state(state)
```

### Example 3: Record Implementation Completion

```python
manager = SessionStateManager()

# After /implement completes successfully
manager.record_implement_completion(
    feature="Add JWT-based user authentication",
    agents_completed=[
        "researcher",
        "planner",
        "test-master",
        "implementer",
        "reviewer"
    ],
    files_modified=[
        "lib/auth/token_manager.py",
        "lib/auth/jwt_handler.py",
        "tests/unit/test_jwt_handler.py",
        "tests/integration/test_authentication.py"
    ]
)
```

### Example 4: Access Session Summary in Agents

```python
manager = SessionStateManager()
summary = manager.get_session_summary()

# Pass summary to agent as context
print(f"Agent context:\n{summary}")

# Agents can reference:
# - Recent files worked on
# - Last completed feature
# - Active tasks
# - Coding conventions
```

### Example 5: Preserve Context Across /clear

Session state automatically persists across `/clear` operations:

```
# Session 1
manager.update_context(
    key_conventions=["Use snake_case"],
    active_tasks=["Add auth"]
)
# User runs /clear (wipes chat context)

# Session 2 (fresh context)
manager = SessionStateManager()
state = manager.load_state()
print(state["session_context"]["key_conventions"])
# Output: ["Use snake_case"]  ← Context preserved!
```

---

## Security Considerations

### Path Traversal (CWE-22)

SessionStateManager rejects paths with `..` at initialization:

```python
# These raise StateError
SessionStateManager("../../../etc/passwd")
SessionStateManager("./../local/state.json")
```

### Symlink Attacks (CWE-59)

Symlinks are validated and rejected:

```python
# Create symlink: ln -s /etc/passwd .claude/local/SESSION_STATE.json
# This raises StateError on load_state()
```

### File Permissions (CWE-732)

State files are created with 0o600 (owner read/write only):

```bash
ls -la .claude/local/SESSION_STATE.json
# -rw------- 1 user group 1234 Jan 19 12:00 SESSION_STATE.json
```

### Atomic Writes (CWE-367)

Uses atomic write pattern (temp file + rename) to prevent TOCTOU issues:

```python
# Internal: temp file + os.rename() prevents corruption on crash
```

### JSON Injection Prevention

State is loaded as JSON, not eval'd or exec'd:

```python
# Safe even if SESSION_STATE.json contains malicious code
state = json.load(f)  # JSON parsing only, no code execution
```

---

## Graceful Degradation

### Corrupted State File

If SESSION_STATE.json is corrupted:

```python
manager = SessionStateManager()
state = manager.load_state()  # Returns default schema, not error!
```

### Missing Parent Directory

Directory is created automatically:

```python
manager = SessionStateManager(".claude/local/SESSION_STATE.json")
# .claude/local/ created if missing
```

### File Already Exists

Existing state is loaded and updated:

```python
manager.save_state(new_state)  # Replaces existing file safely
```

### Permission Errors

Clear error messages guide users:

```python
try:
    manager.save_state(state)
except StateError as e:
    print(f"Permission error: {e}")
```

---

## Performance

### Load Time

```
~2ms to load SESSION_STATE.json (including path validation)
```

### Save Time

```
~5ms to save (includes atomic write + chmod)
```

### Memory Usage

```
~10-50KB typical state object (compression-friendly JSON)
```

### Thread Contention

Reentrant locks prevent blocking with concurrent access:

```python
# Multiple threads can read/update simultaneously
# No deadlocks even with recursive lock acquisition
```

---

## Cross-References

**Related Documentation**:
- [docs/ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) - Session state in architecture overview
- [docs/LIBRARIES.md](LIBRARIES.md) - SessionStateManager API reference
- [docs/SANDBOXING.md](SANDBOXING.md) - `.claude/local/` directory protection
- [.claude/local/OPERATIONS.md](../.claude/local/OPERATIONS.md) - Repo-specific operational procedures

**Related Code**:
- `plugins/autonomous-dev/lib/session_state_manager.py` - Full implementation
- `plugins/autonomous-dev/lib/abstract_state_manager.py` - StateManager ABC
- `plugins/autonomous-dev/lib/security_utils.py` - Path validation utilities

**Related Issues**:
- Issue #220 - StateManager ABC creation
- Issue #244 - `.claude/local/` protection during `/sync`
- Issue #247 - Session state persistence (this issue)
