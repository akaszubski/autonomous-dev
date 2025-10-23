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
