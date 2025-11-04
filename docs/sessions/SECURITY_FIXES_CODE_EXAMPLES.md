# Security Audit - Detailed Code Fixes

**Date**: 2025-11-05
**Auditor**: security-auditor agent
**Report**: SECURITY_AUDIT_PROJECT_MD_UPDATE.md

This document contains exact code changes for the 4 identified vulnerabilities.

---

## FIX #1: Race Condition in Atomic File Operations [HIGH]

**File**: `plugins/autonomous-dev/lib/project_md_updater.py`
**Lines**: 150-181
**Severity**: HIGH
**Effort**: 10 minutes
**Impact**: Prevents PROJECT.md corruption under parallel hook execution

### Current Code (VULNERABLE)

```python
def _atomic_write(self, content: str):
    """Write content to PROJECT.md atomically.

    Uses temp file + rename pattern for atomicity.

    Args:
        content: New content to write

    Raises:
        IOError: If write or rename fails
    """
    temp_path = None

    try:
        # Create temp file path in same directory as target
        # VULNERABILITY: os.getpid() only unique per process, not per invocation
        temp_path = self.project_file.parent / f".PROJECT_{os.getpid()}.tmp"

        # Store the temp path for test verification
        self._last_temp_file = temp_path

        # Write content to temp file using Path.write_text
        # This makes the test's mock work
        temp_path.write_text(content, encoding='utf-8')

        # Atomic rename - but check if file exists first (in case mocked)
        if temp_path.exists():
            temp_path.replace(self.project_file)
        else:
            # If temp file doesn't exist (e.g., mocked write_text),
            # just write directly to target
            self.project_file.write_text(content, encoding='utf-8')

    except Exception as e:
        # Cleanup temp file on error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass

        raise IOError(f"Failed to write PROJECT.md: {e}") from e
```

### Fixed Code

```python
import tempfile  # Add at top of file

def _atomic_write(self, content: str):
    """Write content to PROJECT.md atomically.

    Uses temp file + rename pattern for atomicity.
    Temp file naming guaranteed unique by tempfile module.

    Args:
        content: New content to write

    Raises:
        IOError: If write or rename fails
    """
    temp_path = None

    try:
        # Create guaranteed-unique temp file in same directory as target
        # tempfile.NamedTemporaryFile() ensures uniqueness even under
        # concurrent access and PID recycling
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=self.project_file.parent,
            delete=False,  # Don't auto-delete, we'll rename it
            prefix='.PROJECT_',
            suffix='.tmp',
            encoding='utf-8'
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)

        # Atomic rename
        temp_path.replace(self.project_file)

    except Exception as e:
        # Cleanup temp file on error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass

        raise IOError(f"Failed to write PROJECT.md: {e}") from e
```

### Why This Fix Works

- `tempfile.NamedTemporaryFile()` uses OS-level mechanisms to ensure uniqueness
- Prevents collisions even if:
  - Multiple processes run simultaneously
  - Process IDs are recycled
  - Processes race to write the same file
- File is created atomically by OS (not vulnerable to check-then-act timing)
- `delete=False` allows us to use atomic `replace()` operation

### Testing the Fix

```python
import concurrent.futures
from pathlib import Path
from project_md_updater import ProjectMdUpdater

def test_concurrent_writes():
    """Test that concurrent writes don't corrupt PROJECT.md"""
    project_file = Path("/tmp/test_PROJECT.md")
    project_file.write_text("Initial content")

    # Create updater and perform concurrent writes
    updaters = [
        ProjectMdUpdater(project_file),
        ProjectMdUpdater(project_file),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(u.update_goal_progress, "Goal 1", i * 25)
            for i, u in enumerate(updaters, 1)
        ]
        results = [f.result() for f in futures]

    # Both should succeed without corruption
    assert all(results)
    assert "Goal 1" in project_file.read_text()
```

---

## FIX #2: Agent Name Input Validation [MEDIUM]

**File**: `plugins/autonomous-dev/scripts/invoke_agent.py`
**Lines**: 65-72
**Severity**: MEDIUM
**Effort**: 5 minutes
**Impact**: Prevents path traversal attempts via agent name

### Current Code (VULNERABLE)

```python
def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: invoke_agent.py <agent-name>", file=sys.stderr)
        sys.exit(1)

    agent_name = sys.argv[1]  # VULNERABILITY: No validation

    try:
        output = invoke_agent(agent_name)
        print(output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

### Fixed Code

```python
import re  # Add at top of file
import sys
from pathlib import Path

# Constant for valid agent name pattern
VALID_AGENT_NAME_PATTERN = re.compile(r'^[a-z0-9\-_]+$')

def validate_agent_name(agent_name: str) -> bool:
    """Validate agent name format.

    Args:
        agent_name: Name to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(VALID_AGENT_NAME_PATTERN.match(agent_name))


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: invoke_agent.py <agent-name>", file=sys.stderr)
        sys.exit(1)

    agent_name = sys.argv[1]

    # SECURITY: Validate format BEFORE using in path construction
    if not validate_agent_name(agent_name):
        print(
            f"Error: Invalid agent name: {agent_name}\n"
            f"Expected format: lowercase alphanumeric, hyphens, and underscores\n"
            f"Example: project-progress-tracker",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        output = invoke_agent(agent_name)
        print(output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
```

### Why This Fix Works

- Validates agent name format BEFORE path construction
- Only allows safe characters: lowercase alphanumeric, hyphens, underscores
- Prevents path traversal attempts like:
  - `../../etc/passwd`
  - `..%2f..%2fetc%2fpasswd`
  - `agent\x00.md` (null byte injection)
- Clear error messages guide users to correct format

### Testing the Fix

```python
import subprocess
import sys

def test_valid_agent_names():
    """Test that valid agent names are accepted"""
    valid_names = [
        'researcher',
        'project-progress-tracker',
        'test-master',
        'security-auditor',
        'doc-master-v2',
    ]

    for name in valid_names:
        # Should not raise validation error
        result = subprocess.run(
            [sys.executable, 'invoke_agent.py', name],
            capture_output=True
        )
        # We expect FileNotFoundError (agent doesn't exist), not validation error
        assert 'Invalid agent name' not in result.stderr

def test_invalid_agent_names():
    """Test that invalid agent names are rejected"""
    invalid_names = [
        '../../etc/passwd',
        '../../../bin/sh',
        'agent; rm -rf /',
        'agent/../../secret',
        'UPPERCASE_AGENT',
    ]

    for name in invalid_names:
        result = subprocess.run(
            [sys.executable, 'invoke_agent.py', name],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert 'Invalid agent name' in result.stderr
```

---

## FIX #3: Goal Name Parsing Robustness [MEDIUM]

**File**: `plugins/autonomous-dev/hooks/auto_update_project_progress.py`
**Lines**: 310-330
**Severity**: MEDIUM
**Effort**: 10 minutes
**Impact**: Prevents incorrect goal updates from malformed agent output

### Current Code (VULNERABLE)

```python
def run_hook(
    agent_name: str,
    session_file: Path,
    project_file: Path
):
    """Main hook entry point."""
    # ... [earlier code] ...

    # Extract goal updates
    assessment = parsed["assessment"]
    updates = {}

    for key, value in assessment.items():
        # Convert goal_1 -> Goal 1, goal_2 -> Goal 2, etc.
        if key.startswith("goal_"):
            goal_num = key.replace("goal_", "").replace("_", " ").title()
            goal_name = f"Goal {goal_num}"
            # VULNERABILITY: No validation that goal_name exists
            if isinstance(value, int):
                updates[goal_name] = value

    if not updates:
        print("No goal updates found in assessment", file=sys.stderr)
        return

    # Update PROJECT.md
    print(f"Updating PROJECT.md with {len(updates)} goal(s)...", file=sys.stderr)
    success = update_project_with_rollback(project_file, updates)
```

### Fixed Code

```python
def parse_goal_name_from_assessment(
    key: str,
    project_content: str
) -> Optional[str]:
    """Parse and validate goal name from assessment key.

    Args:
        key: Assessment key (e.g., "goal_1")
        project_content: Content of PROJECT.md to validate against

    Returns:
        Valid goal name, or None if validation fails
    """
    if not key.startswith("goal_"):
        return None

    # Convert goal_1 -> Goal 1, goal_2 -> Goal 2, etc.
    goal_num = key.replace("goal_", "").replace("_", " ").title()
    goal_name = f"Goal {goal_num}"

    # SECURITY: Verify goal exists in PROJECT.md before using
    if goal_name not in project_content:
        return None

    return goal_name


def run_hook(
    agent_name: str,
    session_file: Path,
    project_file: Path
):
    """Main hook entry point."""
    # ... [earlier code] ...

    # Read PROJECT.md content for validation
    if not project_file.exists():
        print(f"Warning: PROJECT.md not found at {project_file}", file=sys.stderr)
        return

    project_content = project_file.read_text()

    # Extract goal updates
    assessment = parsed["assessment"]
    updates = {}

    for key, value in assessment.items():
        # Parse and validate goal name against actual PROJECT.md
        goal_name = parse_goal_name_from_assessment(key, project_content)

        if goal_name is None:
            # Skip invalid or non-existent goals
            print(f"Skipping goal: {key} (not found or invalid)", file=sys.stderr)
            continue

        if isinstance(value, int):
            updates[goal_name] = value

    if not updates:
        print("No valid goal updates found in assessment", file=sys.stderr)
        return

    # Update PROJECT.md
    print(f"Updating PROJECT.md with {len(updates)} goal(s)...", file=sys.stderr)
    success = update_project_with_rollback(project_file, updates)
```

### Why This Fix Works

- Validates goal name exists in actual PROJECT.md before updating
- Prevents updates to non-existent goals
- Gracefully handles malformed agent output
- Clear logging of skipped goals
- Maintains data integrity

### Testing the Fix

```python
def test_goal_name_validation():
    """Test that goal name validation works correctly"""
    project_content = """
## GOALS
- Goal 1: [0%]
- Goal 2: [0%]
- Goal 3: [0%]
"""

    # Valid goals should be found
    assert parse_goal_name_from_assessment("goal_1", project_content) == "Goal 1"
    assert parse_goal_name_from_assessment("goal_2", project_content) == "Goal 2"

    # Invalid goals should return None
    assert parse_goal_name_from_assessment("goal_999", project_content) is None
    assert parse_goal_name_from_assessment("invalid_goal", project_content) is None

def test_malformed_agent_output_handling():
    """Test that malformed agent output is handled gracefully"""
    project_file = Path("/tmp/PROJECT.md")
    project_file.write_text("""
## GOALS
- Goal 1: [0%]
- Goal 2: [0%]
""")

    # Assessment with invalid goal name
    assessment = {
        "goal_1": 25,      # Valid
        "goal_999": 50,    # Invalid - should be skipped
        "goal_invalid": 75,  # Invalid - should be skipped
    }

    updates = {}
    for key, value in assessment.items():
        goal_name = parse_goal_name_from_assessment(key, project_file.read_text())
        if goal_name:
            updates[goal_name] = value

    # Only Goal 1 should be in updates
    assert updates == {"Goal 1": 25}
```

---

## FIX #4: File Permission Management [LOW]

**File**: `plugins/autonomous-dev/lib/project_md_updater.py`
**Lines**: 95-112
**Severity**: LOW
**Effort**: 5 minutes
**Impact**: Ensures backups inherit correct file permissions

### Current Code

```python
def _create_backup(self) -> Path:
    """Create timestamped backup of PROJECT.md.

    Returns:
        Path to backup file

    Format: PROJECT.md.backup.YYYYMMDD-HHMMSS
    """
    if not self.project_file.exists():
        raise FileNotFoundError(
            f"PROJECT.md not found: {self.project_file}\n"
            f"Cannot create backup of non-existent file"
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = self.project_file.parent / f"{self.project_file.name}.backup.{timestamp}"

    # Copy content to backup
    content = self.project_file.read_text()
    backup_path.write_text(content)  # ISSUE: Doesn't preserve permissions

    self.backup_file = backup_path
    return backup_path
```

### Fixed Code

```python
import stat  # Add at top of file
from shutil import copyfile  # Add at top of file

def _create_backup(self) -> Path:
    """Create timestamped backup of PROJECT.md.

    Backups inherit original file permissions.

    Returns:
        Path to backup file

    Format: PROJECT.md.backup.YYYYMMDD-HHMMSS
    """
    if not self.project_file.exists():
        raise FileNotFoundError(
            f"PROJECT.md not found: {self.project_file}\n"
            f"Cannot create backup of non-existent file"
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = self.project_file.parent / f"{self.project_file.name}.backup.{timestamp}"

    # Copy content to backup
    content = self.project_file.read_text()
    backup_path.write_text(content)

    # SECURITY: Preserve original file permissions on backup
    try:
        original_mode = self.project_file.stat().st_mode
        backup_path.chmod(original_mode)
    except (OSError, AttributeError) as e:
        # Log but don't fail if we can't preserve permissions
        # (e.g., on filesystems that don't support chmod)
        print(
            f"Warning: Could not preserve file permissions on backup: {e}",
            file=sys.stderr
        )

    self.backup_file = backup_path
    return backup_path
```

### Why This Fix Works

- Preserves original file permissions on backups
- Ensures backups are as secure as originals
- Handles filesystems that don't support chmod gracefully
- Non-blocking (logs warning but doesn't fail)

---

## FIX #5: Environment Variable Documentation [LOW]

**File**: `plugins/autonomous-dev/hooks/auto_update_project_progress.py`
**Lines**: 1-45 (docstring)
**Severity**: LOW
**Effort**: 5 minutes
**Impact**: Documents required environment variables

### Current Code

```python
#!/usr/bin/env python3
"""
SubagentStop Hook - Auto-Update PROJECT.md Progress After Pipeline

This hook automatically updates PROJECT.md goal progress after the doc-master
agent completes, marking the end of the /auto-implement pipeline.

Hook Type: SubagentStop
Trigger: After doc-master agent completes
Condition: All 7 agents completed successfully

Workflow:
1. Check if doc-master just completed (trigger condition)
2. Verify pipeline is complete (all 7 agents ran)
3. Invoke project-progress-tracker agent to assess progress
4. Parse YAML output from agent
5. Update PROJECT.md atomically with new progress
6. Create backup and handle rollback on failure

Environment Variables (provided by Claude Code):
    CLAUDE_AGENT_NAME - Name of the subagent that completed
    CLAUDE_AGENT_OUTPUT - Output from the subagent
    CLAUDE_AGENT_STATUS - Status: "success" or "error"

Output:
    Updates PROJECT.md with goal progress
    Logs actions to session file

Date: 2025-11-04
Feature: PROJECT.md auto-update
Agent: implementer
"""
```

### Fixed Code

```python
#!/usr/bin/env python3
"""
SubagentStop Hook - Auto-Update PROJECT.md Progress After Pipeline

This hook automatically updates PROJECT.md goal progress after the doc-master
agent completes, marking the end of the /auto-implement pipeline.

Hook Type: SubagentStop
Trigger: After doc-master agent completes
Condition: All 7 agents completed successfully

Workflow:
1. Check if doc-master just completed (trigger condition)
2. Verify pipeline is complete (all 7 agents ran)
3. Invoke project-progress-tracker agent to assess progress
4. Parse YAML output from agent
5. Update PROJECT.md atomically with new progress
6. Create backup and handle rollback on failure

Environment Variables (provided by Claude Code):
    CLAUDE_AGENT_NAME - Name of the subagent that completed (required)
    CLAUDE_AGENT_OUTPUT - Output from the subagent (required)
    CLAUDE_AGENT_STATUS - Status: "success" or "error" (required)

Expected Directory Structure:
    docs/sessions/ - Contains session tracking files
    .claude/PROJECT.md - Project file to update

Output:
    Updates PROJECT.md with goal progress
    Logs actions to session file (/dev/stderr)

Error Handling:
    Non-fatal: Errors logged to stderr, hook continues (doesn't block workflow)
    Fallback: If progress tracker fails, PROJECT.md not updated (safe)
    Rollback: If update fails, automatic rollback to backup

Security Notes:
    - Uses yaml.safe_load() to prevent code injection
    - Validates goal names against actual PROJECT.md
    - Atomic writes prevent corruption
    - Timestamped backups enable rollback

Date: 2025-11-04
Feature: PROJECT.md auto-update
Agent: implementer
"""
```

---

## Summary of Changes

| Fix | File | Lines | Priority | Effort | Impact |
|-----|------|-------|----------|--------|--------|
| Race Condition | project_md_updater.py | 150-181 | HIGH | 10 min | Prevents data corruption |
| Agent Name Validation | invoke_agent.py | 65-72 | MEDIUM | 5 min | Prevents path traversal |
| Goal Name Validation | auto_update_project_progress.py | 310-330 | MEDIUM | 10 min | Prevents bad updates |
| File Permissions | project_md_updater.py | 95-112 | LOW | 5 min | Improves security posture |
| Documentation | auto_update_project_progress.py | 1-45 | LOW | 5 min | Improves maintainability |

**Total Implementation Time**: ~35 minutes
**Total Testing Time**: ~20 minutes

---

## Implementation Checklist

- [ ] Fix #1: Race condition in atomic writes
  - [ ] Update `_atomic_write()` method
  - [ ] Import `tempfile` at top of file
  - [ ] Test concurrent writes
- [ ] Fix #2: Agent name validation
  - [ ] Add `VALID_AGENT_NAME_PATTERN` constant
  - [ ] Add `validate_agent_name()` function
  - [ ] Update `main()` to validate before path construction
  - [ ] Test with valid and invalid names
- [ ] Fix #3: Goal name validation
  - [ ] Add `parse_goal_name_from_assessment()` function
  - [ ] Update `run_hook()` to validate goals
  - [ ] Test with valid and invalid goals
- [ ] Fix #4: File permissions
  - [ ] Import `stat` module
  - [ ] Update `_create_backup()` to preserve permissions
  - [ ] Test permission preservation
- [ ] Fix #5: Documentation
  - [ ] Update module docstring
  - [ ] Add environment variable documentation
  - [ ] Add error handling notes
  - [ ] Add security notes

---

**Audit Complete**
**Date**: 2025-11-05
**Status**: Ready for implementation
