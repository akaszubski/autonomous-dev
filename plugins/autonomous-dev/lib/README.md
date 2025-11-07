# autonomous-dev v2.0 - Core Library

**Version**: 2.0.0-alpha
**Status**: Weeks 1-3 Complete (Infrastructure Ready)
**Last Updated**: 2025-10-23

This directory contains the complete infrastructure for autonomous-dev v2.0's orchestration system.

## Modules

### `artifacts.py`
**Purpose**: Artifact management and validation

**Features**:
- Create/read/write workflow artifacts (manifest, research, architecture, etc.)
- Validate artifacts against schemas
- Track workflow progress
- Manage artifact directories

**Usage**:
```python
from lib.artifacts import ArtifactManager, generate_workflow_id

manager = ArtifactManager()
workflow_id = generate_workflow_id()

# Create manifest
manager.create_manifest_artifact(
    workflow_id=workflow_id,
    request="Implement feature X",
    alignment_data={'validated': True},
    workflow_plan={'agents': ['researcher', 'planner']}
)

# Read artifact
manifest = manager.read_artifact(workflow_id, 'manifest')
```

### `logging_utils.py`
**Purpose**: Structured logging and observability

**Features**:
- Per-agent workflow logging
- Structured event logging (JSON)
- Decision logging with rationale
- Performance metrics tracking
- Alignment validation logging
- Progress tracking across agents

**Usage**:
```python
from lib.logging_utils import WorkflowLogger, WorkflowProgressTracker

logger = WorkflowLogger(
    workflow_id="20251023_123456",
    agent_name="orchestrator"
)

# Log events
logger.log_event('agent_start', 'Orchestrator started')
logger.log_decision(
    'Use researcher for web search',
    'Request requires external research'
)
logger.log_alignment_check(True, 'Aligns with PROJECT.md goals')

# Track progress
tracker = WorkflowProgressTracker(workflow_id)
tracker.update_progress('researcher', 'in_progress', 25)
```

### `test_framework.py`
**Purpose**: Testing utilities for agent behavior validation

**Features**:
- Mock artifacts for testing
- Mock PROJECT.md for alignment tests
- Artifact validation utilities
- Pytest fixtures for common scenarios

**Usage**:
```python
from lib.test_framework import MockArtifact, MockProjectMd, ArtifactValidator

# Create mock artifacts
artifact = MockArtifact({
    'version': '2.0',
    'agent': 'orchestrator',
    'workflow_id': 'test_123',
    'status': 'completed'
})

# Validate
is_valid, error = ArtifactValidator.validate(artifact.data)
assert is_valid

# Create mock PROJECT.md
project_md = MockProjectMd(
    goals=["Improve security"],
    scope_included=["Authentication"],
    constraints=["No third-party auth"]
)
```

### `orchestrator.py` (Week 2)
**Purpose**: Master coordinator for autonomous workflows

**Features**:
- PROJECT.md parsing (GOALS, SCOPE, CONSTRAINTS)
- Semantic alignment validation
- Workflow initialization
- Artifact management integration
- Progress tracking

**Usage**:
```python
from lib.orchestrator import Orchestrator

orchestrator = Orchestrator()

# Start workflow with alignment validation
success, message, workflow_id = orchestrator.start_workflow(
    "implement user authentication with JWT tokens"
)

if success:
    print(f"Workflow {workflow_id} started")
    # Continue with agent pipeline...
```

### `checkpoint.py` (Week 2)
**Purpose**: Checkpoint/resume system for workflow resilience

**Features**:
- Create checkpoints after each agent
- Load and validate checkpoints
- Resume interrupted workflows
- List resumable workflows
- Generate resume plans

**Usage**:
```python
from lib.checkpoint import CheckpointManager

manager = CheckpointManager()

# Create checkpoint
manager.create_checkpoint(
    workflow_id=workflow_id,
    completed_agents=['orchestrator', 'researcher'],
    current_agent='planner',
    artifacts_created=['manifest.json', 'research.json']
)

# Resume workflow
resumable = manager.list_resumable_workflows()
resume_plan = manager.get_resume_plan(workflow_id)
```

### `test_workflow_v2.py` (Week 3)
**Purpose**: Complete workflow test suite

**Features**:
- Test 1: Workflow initialization
- Test 2: Checkpoint creation
- Test 3: Artifact handoff
- Test 4: Logging & observability

**Usage**:
```bash
python plugins/autonomous-dev/lib/test_workflow_v2.py

# Runs all tests:
# ✅ Test 1: Workflow initialization
# ✅ Test 2: Checkpoint creation
# ✅ Test 3: Artifact handoff
# ✅ Test 4: Logging
```

### `performance_profiler.py` (v3.6.0+)
**Purpose**: Performance timing and bottleneck detection for /auto-implement agents

**Features**:
- Context manager interface for minimal-overhead timing (profiling cost: <5%)
- JSON logging to `logs/performance_metrics.json` (newline-delimited format)
- Aggregate metrics calculation (min, max, avg, p95) per agent
- Thread-safe concurrent logging with file locking
- ISO 8601 timestamps for cross-system compatibility
- Bottleneck detection and performance reporting

**Public Functions**:
- `PerformanceTimer` - Context manager class for timing with automatic logging
- `calculate_aggregate_metrics(durations)` - Compute min/max/avg/p95 from samples
- `load_metrics_from_log(log_path, skip_corrupted=True)` - Load metrics from JSON log
- `aggregate_metrics_by_agent(metrics, agent_name=None)` - Group metrics by agent
- `generate_performance_report(metrics, feature=None)` - Human-readable performance report
- `generate_summary_report(metrics_by_agent)` - Summary statistics by agent
- `identify_bottlenecks(metrics_by_agent, baseline_minutes=None, threshold_multiplier=1.5)` - Find slow agents
- `measure_profiler_overhead(iterations=1000)` - Validate profiling cost (<5%)

**Usage**:
```python
from performance_profiler import PerformanceTimer, calculate_aggregate_metrics, load_metrics_from_log, aggregate_metrics_by_agent, generate_performance_report

# Time a single agent execution
with PerformanceTimer("researcher", "Add user authentication", log_to_file=True) as timer:
    result = agent.execute()

print(f"Duration: {timer.duration:.2f}s")

# Load and aggregate metrics from multiple runs
metrics = load_metrics_from_log()
aggregates = aggregate_metrics_by_agent(metrics)

# Generate performance report
report = generate_performance_report(metrics, feature="Add user authentication")
print(report)

# Identify bottlenecks
baselines = {"researcher": 300, "planner": 180}  # seconds
bottlenecks = identify_bottlenecks(aggregates, baselines)
print(f"Slow agents: {bottlenecks}")
```

**Integration with /auto-implement**:
- Each agent execution wrapped in PerformanceTimer context manager
- Timing data logged to `logs/performance_metrics.json` after each agent completes
- Session files include aggregate metrics for analysis
- Performance dashboard in final completion report identifies slowest agents
- Enables Phase 7+ optimization decisions based on real profiling data

**Performance Characteristics**:
- Profiling overhead: <5% (validated by `measure_profiler_overhead()`)
- File I/O: Minimal impact via newline-delimited JSON append
- Memory: Minimal (<1MB for 1000 metrics)
- Thread-safety: File lock ensures concurrent writes don't corrupt log

**Design Notes**:
- Uses `time.perf_counter()` for high-resolution timing (microsecond precision)
- Uses `datetime.now()` for wall-clock timestamps in ISO 8601 format
- Gracefully handles logging failures (doesn't break main workflow)
- Skips empty/corrupted log lines by default (skip_corrupted=True)
- P95 percentile useful for identifying performance stability issues
- Bottleneck detection uses 75th percentile or baseline comparison

**Related Phase 6 Metrics**:
- Test coverage: 71/78 tests passing (91%)
- Known limitations: 7 tests require full /auto-implement integration context
- Library size: 539 lines including comprehensive docstrings
- Performance impact: Sub-millisecond overhead per timing operation

**Security Hardening** (v3.6.0+):
- **CWE-20: Improper Input Validation** - agent_name parameter
  - Validation: Alphanumeric + hyphen/underscore only, max 256 characters
  - Pattern: `^[a-zA-Z0-9_-]+$`
  - Raises `ValueError` with detailed message if invalid
- **CWE-22: Path Traversal** - log_path parameter
  - Validation: Whitelist-based 4-layer defense-in-depth
  - Rejects '..' paths, absolute paths, symlinks, null bytes
  - Restricts to `logs/` directory only (relative to project root)
  - Auto-creates `logs/` directory if needed with safe permissions
- **CWE-117: Log Injection** - feature parameter
  - Validation: Control character filtering (newlines, tabs, NUL, etc.)
  - Max length: 10,000 characters (prevents log bloat attacks)
  - Raises `ValueError` if control characters detected
- **Audit Logging**: All validation failures logged via `security_utils.audit_log()`
  - Destination: `logs/security_audit.log` with rotation (10MB, 5 backups)
  - Format: Timestamp, component, action, error details
- **Test Coverage**: 92 security tests (92/92 passing, 100% success rate)
  - Unit tests: `tests/unit/lib/test_performance_profiler.py`
  - Coverage: Input validation, boundary conditions, error handling
- **Usage Pattern**:
  ```python
  # Validation happens automatically in PerformanceTimer.__init__()
  # ValueError raised with detailed message on invalid input
  try:
      with PerformanceTimer("../../../etc/passwd", "feature", log_to_file=True):
          pass
  except ValueError as e:
      # Error includes what failed, why, and security docs reference
      print(e)  # ValueError: agent_name invalid...
  ```

### `git_operations.py` (v3.3.0+)
**Purpose**: Consent-based git automation for /auto-implement Step 8

**Features**:
- Prerequisite validation (git installed, repo exists, config set)
- Merge conflict detection
- Detached HEAD state checking
- Automatic change staging and committing
- Feature branch creation and pushing
- Graceful degradation (commit succeeds even if push fails)
- Security-first (no credential logging, validates before operations)

**Public Functions**:
- `validate_git_repo()` - Check git availability and repository validity
- `check_git_config()` - Verify user.name and user.email are configured
- `detect_merge_conflict()` - Detect unresolved merge conflicts
- `is_detached_head()` - Check for detached HEAD state
- `has_uncommitted_changes()` - Check for uncommitted changes
- `stage_all_changes()` - Stage all modified files
- `commit_changes(message)` - Commit staged changes with message
- `get_remote_name()` - Get default remote name
- `push_to_remote(branch, remote)` - Push to remote with timeout handling
- `create_feature_branch(branch_name)` - Create and switch to feature branch
- `auto_commit_and_push(commit_message, branch, push=True)` - High-level orchestration function

**Usage**:
```python
from git_operations import auto_commit_and_push

# Commit and push (with user consent)
result = auto_commit_and_push(
    commit_message='feat: add authentication',
    branch='main',
    push=True  # Set False to commit-only
)

if result['success']:
    print(f"Committed: {result['commit_sha']}")
    if result['pushed']:
        print("Pushed to remote")
else:
    print(f"Error: {result['error']}")

# Or use individual functions for fine-grained control
from git_operations import validate_git_repo, check_git_config, stage_all_changes

is_valid, error = validate_git_repo()
is_configured, error = check_git_config()
success, error = stage_all_changes()
```

**Integration with /auto-implement**:
- Called from Step 8 (Git Operations)
- Offers user consent before operations
- Prerequisite checks before offering git automation
- Graceful degradation if git unavailable or prerequisites not met
- Example from auto-implement.md Step 8:
  ```python
  from git_operations import auto_commit_and_push

  # User agreed to commit and push
  result = auto_commit_and_push(commit_msg, current_branch, push=True)
  if result['success'] and result['pushed']:
      print(f"Committed and pushed")
  elif result['success']:
      print(f"Committed but push failed: {result['error']}")
  ```

**Return Format** (auto_commit_and_push):
```python
{
    'success': bool,        # True if commit succeeded (push failure is graceful)
    'commit_sha': str,      # Commit SHA if successful, empty string otherwise
    'pushed': bool,         # True if push succeeded
    'error': str            # Error message if any, empty string otherwise
}
```

**Error Handling**:
- Returns descriptive error messages
- Validates prerequisites before attempting operations
- Handles subprocess timeouts (30s default for push)
- Detects and reports merge conflicts, detached HEAD, missing config
- Never logs credentials or sensitive data
- Gracefully degrades (commit success not blocked by push failure)

## Architecture

These modules implement the **foundation** for autonomous-dev v2.0:

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                         │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Hooks (Auto-detection)                     │
│  - UserPromptSubmit-orchestrator.sh                     │
│  - PreToolUseWrite-protect-sensitive.sh                 │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│            Orchestrator (Coming in Week 2)              │
│  Uses:                                                  │
│  - artifacts.py (create workflow, write manifests)      │
│  - logging_utils.py (log decisions, track progress)     │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│              8-Agent Pipeline                           │
│  orchestrator → researcher → planner → test-master →    │
│  implementer → [reviewer ‖ security ‖ docs]            │
│                                                         │
│  Each agent:                                            │
│  - Reads artifacts via artifacts.py                     │
│  - Logs decisions via logging_utils.py                  │
│  - Writes output artifacts via artifacts.py             │
└─────────────────────────────────────────────────────────┘
```

## Testing

Run tests for this module:

```bash
# Test artifact management
python plugins/autonomous-dev/lib/artifacts.py

# Test logging
python plugins/autonomous-dev/lib/logging_utils.py

# Test framework tests
python plugins/autonomous-dev/lib/test_framework.py
```

## Implementation Status (Weeks 1-3)

### Week 1: Foundation ✅ COMPLETE
- [x] Directory structure (`.claude/artifacts`, `.claude/logs`)
- [x] Hooks (UserPromptSubmit, PreToolUseWrite)
- [x] Test framework skeleton
- [x] Logging infrastructure
- [x] Artifact management

**Deliverables**: 1,222 lines of code, 7 files

### Week 2: Orchestrator Core ✅ COMPLETE
- [x] Orchestrator implementation
- [x] PROJECT.md parser
- [x] Semantic alignment validator
- [x] Checkpoint/resume system
- [x] Progress streaming
- [x] Retry framework

**Deliverables**: 759 lines of code, 2 files

### Week 3: Pipeline Foundation ✅ COMPLETE
- [x] Command interface (`/auto-implement-v2`)
- [x] Enhanced PROJECT.md parser
- [x] Workflow test suite (4 tests)
- [x] Artifact schema examples
- [x] Documentation complete

**Deliverables**: 750 lines of code, 3 files

### Cumulative Status

- **Total Code**: 2,731 lines
- **Total Documentation**: 2,660 lines
- **Test Coverage**: 100% (19/19 tests passing)
- **Status**: Infrastructure ready for agent integration

## Next Steps (Week 4+)

**Priority 1: Agent Invocation** (Week 4-5)
- [ ] Integrate Task tool API
- [ ] Update researcher.md for v2.0
- [ ] Test orchestrator → researcher pipeline
- [ ] Validate artifact handoff with real agents

**Priority 2: Sequential Pipeline** (Week 6-7)
- [ ] Update planner, test-master, implementer for v2.0
- [ ] Test full sequential pipeline
- [ ] Validate TDD workflow (tests before code)

**Priority 3: Parallel Validators** (Week 8-10)
- [ ] Implement parallel execution
- [ ] Update reviewer, security, docs for v2.0
- [ ] Measure speedup (target: 20-30%)

## References

- **Specification**: `AUTONOMOUS_DEV_V2_MASTER_SPEC.md`
- **Implementation Status**: `docs/V2_IMPLEMENTATION_STATUS.md`
- **Week 1 Validation**: `docs/WEEK1_VALIDATION.md`
- **Week 2 Validation**: `docs/WEEK2_VALIDATION.md`
- **Week 3 Validation**: `docs/WEEK3_VALIDATION.md`
- **Architecture**: `docs/DOGFOODING-ARCHITECTURE.md`

---

**Weeks 1-3 Complete**: Infrastructure ready for Week 4+ agent integration
