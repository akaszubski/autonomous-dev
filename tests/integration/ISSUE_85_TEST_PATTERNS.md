# Test Patterns Reference - Issue #85 Checkpoint Portability Tests

Quick reference for understanding the test patterns in `test_auto_implement_checkpoint_portability.py`.

---

## Test Execution Pattern

All tests use **subprocess** to execute heredoc Python code:

```python
# 1. Create test script with heredoc logic
test_script = temp_repo / "test.py"
test_script.write_text(checkpoint_heredoc_template)

# 2. Execute via subprocess (like bash would)
result = subprocess.run(
    [sys.executable, str(test_script)],
    cwd=str(temp_repo),
    capture_output=True,
    text=True,
    timeout=10
)

# 3. Assert on output and exit code
assert "CHECKPOINT ERROR" not in result.stdout
assert result.returncode == 0
```

**Why subprocess?** Because we're testing bash heredocs, not Python modules.

---

## Fixture Pattern: temp_repo

Creates a complete repository structure for testing:

```python
@pytest.fixture
def temp_repo(tmp_path):
    """Create temporary git repository with full structure."""
    # Markers
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude").mkdir()
    
    # Plugin structure
    lib_dir = tmp_path / "plugins" / "autonomous-dev" / "lib"
    lib_dir.mkdir(parents=True)
    
    # Copy real files (path_utils, security_utils, agent_tracker)
    # ...
    
    return tmp_path
```

**Benefits**:
- Isolated from real repository
- Repeatable across test runs
- Can simulate different directory structures

---

## Path Detection Test Pattern

Tests that checkpoints find project root from different locations:

```python
def test_checkpoint_runs_from_subdirectory(temp_repo, checkpoint_template):
    # Arrange: Create nested directory
    sessions_dir = temp_repo / "docs" / "sessions"
    test_script = sessions_dir / "test.py"
    test_script.write_text(checkpoint_template)
    
    # Act: Execute from subdirectory (not root!)
    result = subprocess.run(
        [sys.executable, str(test_script)],
        cwd=str(sessions_dir),  # <-- Key: run from nested dir
        capture_output=True,
        text=True
    )
    
    # Assert: Successfully found root by searching upward
    assert "Could not find project root" not in result.stdout
```

**Key**: `cwd=str(sessions_dir)` simulates running checkpoint from subdirectory.

---

## Import Logic Test Pattern

Tests that sys.path modifications enable imports:

```python
def test_imports_agent_tracker_after_path_detection(temp_repo):
    # Arrange: Checkpoint that imports AgentTracker
    test_code = """
import sys
from pathlib import Path

project_root = Path.cwd()
sys.path.insert(0, str(project_root / "scripts"))

from agent_tracker import AgentTracker  # <-- Should work
tracker = AgentTracker()
print("SUCCESS")
"""
    test_script = temp_repo / "test.py"
    test_script.write_text(test_code)
    
    # Act: Execute
    result = subprocess.run([sys.executable, str(test_script)], ...)
    
    # Assert: Import succeeded
    assert "ImportError" not in result.stderr
    assert "SUCCESS" in result.stdout
```

**Key**: Tests that sys.path modifications actually work.

---

## Fallback Logic Test Pattern

Tests graceful degradation when path_utils unavailable:

```python
def test_fallback_works_without_path_utils(tmp_path):
    # Arrange: Repository WITHOUT path_utils.py
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    test_code = """
try:
    from path_utils import get_project_root  # Will fail
    method = "path_utils"
except ImportError:
    # Fallback: Manual search
    from pathlib import Path
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            root = parent
            break
    method = "fallback"

print(f"SUCCESS: {method}")
"""
    
    # Act: Execute
    result = subprocess.run(...)
    
    # Assert: Fallback worked
    assert "SUCCESS: fallback" in result.stdout
```

**Key**: Simulates missing dependency, validates fallback works.

---

## Error Handling Test Pattern

Tests clear error messages when things fail:

```python
def test_clear_error_when_no_git_marker(tmp_path):
    # Arrange: Directory WITHOUT .git or .claude
    test_script = tmp_path / "test.py"
    test_script.write_text(checkpoint_template)
    
    # Act: Execute (will fail)
    result = subprocess.run(...)
    
    # Assert: Clear, helpful error message
    assert "Could not find project root" in result.stdout
    assert ".git or .claude marker not found" in result.stdout
    assert "autonomous-dev repository" in result.stdout
    assert result.returncode != 0  # Non-zero exit
```

**Key**: Validates user gets helpful guidance, not cryptic errors.

---

## Integration Test Pattern

Tests full end-to-end checkpoint execution:

```python
def test_checkpoint1_executes_successfully(temp_repo):
    # Arrange: Full repository + valid session file
    session_file = temp_repo / "docs" / "sessions" / "test.json"
    session_data = {
        "session_id": "test",
        "agents": [
            {"agent": "researcher", "status": "completed"}
        ]
    }
    session_file.write_text(json.dumps(session_data))
    
    # Copy real agent_tracker.py and security_utils.py
    # ...
    
    # Act: Execute checkpoint heredoc
    test_script = temp_repo / "test.py"
    test_script.write_text(checkpoint1_heredoc_template)
    result = subprocess.run(...)
    
    # Assert: Checkpoint executed (may pass/fail based on data)
    assert "PARALLEL EXPLORATION" in result.stdout or result.returncode == 0
```

**Key**: Uses real AgentTracker code, not mocks.

---

## Regression Test Pattern

Tests that detect if hardcoded paths creep back in:

```python
def test_auto_implement_md_has_no_hardcoded_paths():
    # Arrange: Read actual file
    auto_implement = PROJECT_ROOT / "plugins/.../auto-implement.md"
    content = auto_implement.read_text()
    
    # Act: Search for hardcoded patterns
    hardcoded_patterns = [
        "/Users/akaszubski",
        "C:\\Users\\",
        "/home/specific-user"
    ]
    
    # Assert: No hardcoded paths found
    for pattern in hardcoded_patterns:
        assert pattern not in content, (
            f"Found hardcoded path '{pattern}'. "
            f"Use path_utils.get_project_root() instead."
        )
```

**Key**: This test FAILS during TDD red phase, PASSES after implementation.

---

## Fixture Template Pattern

Provides fixed checkpoint heredocs for testing:

```python
@pytest.fixture
def checkpoint1_heredoc_template():
    """Template for CHECKPOINT 1 (line 112).
    
    This is the FIXED version we want to test.
    """
    return """
import sys
from pathlib import Path

# Dynamically detect project root
try:
    from path_utils import get_project_root
    project_root = get_project_root()
except ImportError:
    # Fallback: Manual search
    current = Path.cwd()
    project_root = None
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / ".claude").exists():
            project_root = parent
            break
    if not project_root:
        raise FileNotFoundError("Could not find project root")

# Add scripts to sys.path
sys.path.insert(0, str(project_root / "scripts"))

# Import and execute
from agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_exploration()
print(f"{'✅ SUCCESS' if success else '❌ FAILED'}")
"""
```

**Key**: Tests the FIXED version, not current broken version.

---

## Cross-Platform Test Pattern

Tests pathlib portability across OS:

```python
def test_pathlib_handles_posix_paths(tmp_path):
    """Test pathlib works with POSIX-style paths."""
    # Arrange: POSIX path with forward slashes
    posix_style = tmp_path / "some" / "nested" / "path"
    posix_style.mkdir(parents=True)
    
    # Act: Resolve path
    resolved = posix_style.resolve()
    
    # Assert: Works regardless of platform
    assert resolved.exists()
    assert resolved.is_absolute()

@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_pathlib_handles_windows_paths():
    """Test pathlib normalizes Windows paths."""
    # Arrange: Windows backslash path
    win_path = Path("C:\\Users\\test\\file.txt")
    
    # Act: Normalize via pathlib
    normalized = win_path.as_posix()
    
    # Assert: Converted to forward slashes
    assert normalized == "C:/Users/test/file.txt"
```

**Key**: Uses `@pytest.mark.skipif` for platform-specific tests.

---

## Common Assertions

### Success Assertions
```python
assert "CHECKPOINT ERROR" not in result.stdout
assert result.returncode == 0
assert "SUCCESS" in result.stdout
```

### Error Assertions
```python
assert "Could not find project root" in result.stdout
assert result.returncode != 0
assert "ImportError" not in result.stderr
```

### Import Assertions
```python
assert "ModuleNotFoundError" not in result.stderr
assert "from agent_tracker import AgentTracker" not in result.stderr
```

### Regex Assertions (if needed)
```python
import re
assert re.search(r"PARALLEL EXPLORATION: (SUCCESS|FAILED)", result.stdout)
```

---

## Test Organization

### Categories (6 total)
1. **Path Detection** - Finding project root
2. **Import Logic** - sys.path modifications
3. **Cross-Platform** - Windows/POSIX portability
4. **Error Handling** - Graceful failures
5. **Integration** - End-to-end execution
6. **Regression** - Prevent hardcoded paths returning

### Naming Convention
- `test_<category>_<scenario>` (e.g., `test_checkpoint_runs_from_subdirectory`)
- `Test<Category>` class groups (e.g., `class TestPathDetection`)

### File Structure
```
test_auto_implement_checkpoint_portability.py
├── Module docstring (TDD context)
├── Imports
├── Fixtures (temp_repo, checkpoint templates)
├── Category 1: Path Detection Tests
├── Category 2: Import Logic Tests
├── Category 3: Cross-Platform Tests
├── Category 4: Error Handling Tests
├── Category 5: Integration Tests
├── Category 6: Regression Tests
└── Summary docstring
```

---

## Running Tests

### All tests
```bash
pytest tests/integration/test_auto_implement_checkpoint_portability.py -v
```

### Single category
```bash
pytest tests/integration/test_auto_implement_checkpoint_portability.py::TestPathDetection -v
```

### Single test
```bash
pytest tests/integration/test_auto_implement_checkpoint_portability.py::TestPathDetection::test_checkpoint_runs_from_project_root -v
```

### With coverage
```bash
pytest tests/integration/test_auto_implement_checkpoint_portability.py --cov=plugins/autonomous-dev/lib/path_utils --cov-report=term-missing
```

---

## Expected Results

### TDD Red Phase (Current)
```
PASSED:  16 tests (infrastructure works)
FAILED:   2 tests (regression detection - expected)
SKIPPED:  1 test  (Windows-specific)
```

### TDD Green Phase (After Implementation)
```
PASSED:  18 tests (all working!)
SKIPPED:  1 test  (Windows-specific)
```

---

## Key Takeaways

1. **Use subprocess** for testing bash heredoc execution
2. **Create isolated fixtures** (temp_repo) for reproducibility
3. **Test the fixed version**, not current broken state
4. **Validate error messages**, not just success cases
5. **Platform-specific tests** use @pytest.mark.skipif
6. **Regression tests** ensure hardcoded paths don't return

This test suite validates that the portable checkpoint logic will work correctly across all platforms and scenarios.
