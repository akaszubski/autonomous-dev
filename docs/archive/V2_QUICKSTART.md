# autonomous-dev v2.0 - Quick Start Guide

**Version**: 2.0.0-alpha
**Status**: Infrastructure Complete (Weeks 1-3)
**Last Updated**: 2025-10-23

---

## What is v2.0?

autonomous-dev v2.0 is a **complete redesign** that adopts Claude Code 2.0 best practices:

- ✅ **PROJECT.md-first governance** (zero tolerance for drift)
- ✅ **Artifact-based communication** (auditable, testable, debuggable)
- ✅ **Checkpoint/resume** (resilient to interruptions)
- ✅ **Semantic alignment** (understands domain relationships)
- ✅ **Transparent architecture** (markdown agents, JSON artifacts)

**Current Status**: Infrastructure complete, agent integration in progress (Week 4+)

---

## What's Working Right Now

### 1. PROJECT.md Parsing & Validation ✅

```python
from plugins.autonomous_dev.lib.orchestrator import Orchestrator

# Initialize orchestrator
orchestrator = Orchestrator()

# The orchestrator reads .claude/PROJECT.md and parses:
# - GOALS: What you're trying to achieve
# - SCOPE: What's in/out of scope
# - CONSTRAINTS: Technical and business limitations

print(f"Goals: {len(orchestrator.project_md['goals'])}")
print(f"Constraints: {len(orchestrator.project_md['constraints'])}")
```

### 2. Alignment Validation ✅

```python
# Start a workflow - validates alignment automatically
success, message, workflow_id = orchestrator.start_workflow(
    "implement user authentication with JWT tokens"
)

if success:
    print(f"✅ Aligned! Workflow {workflow_id} created")
else:
    print(f"❌ Blocked: {message}")
```

**Test it**:
```bash
cd /path/to/autonomous-dev
python plugins/autonomous-dev/lib/orchestrator.py
```

### 3. Artifact System ✅

```python
from plugins.autonomous_dev.lib.artifacts import ArtifactManager

manager = ArtifactManager()

# Create manifest
manifest_path = manager.create_manifest_artifact(
    workflow_id="20251023_123456",
    request="implement user authentication",
    alignment_data={'validated': True, 'matches_goals': ['Improve security']},
    workflow_plan={'agents': ['researcher', 'planner']}
)

# Read manifest
manifest = manager.read_artifact("20251023_123456", 'manifest')
print(f"Request: {manifest['request']}")
```

**Test it**:
```bash
python plugins/autonomous-dev/lib/artifacts.py
```

### 4. Checkpoint/Resume ✅

```python
from plugins.autonomous_dev.lib.checkpoint import CheckpointManager

manager = CheckpointManager()

# Create checkpoint
manager.create_checkpoint(
    workflow_id="20251023_123456",
    completed_agents=['orchestrator', 'researcher'],
    current_agent='planner',
    artifacts_created=['manifest.json', 'research.json']
)

# List resumable workflows
resumable = manager.list_resumable_workflows()
for workflow in resumable:
    print(f"Workflow {workflow['workflow_id']}: {workflow['progress']}")

# Get resume plan
plan = manager.get_resume_plan("20251023_123456")
print(f"Next agent: {plan['next_agent']}")
```

**Test it**:
```bash
python plugins/autonomous-dev/lib/checkpoint.py
```

### 5. Complete Workflow Simulation ✅

Run the full test suite to see all components working together:

```bash
cd /path/to/autonomous-dev
python plugins/autonomous-dev/lib/test_workflow_v2.py
```

**What it tests**:
1. ✅ Workflow initialization with PROJECT.md
2. ✅ Checkpoint creation and validation
3. ✅ Artifact handoff between agents
4. ✅ Logging with decision rationale

**Expected output**:
```
╔════════════════════════════════════════════════════════╗
║     AUTONOMOUS-DEV V2.0 WORKFLOW TEST                 ║
╚════════════════════════════════════════════════════════╝

TEST 1: Workflow Initialization
✓ Orchestrator initialized
✓ Workflow started
✓ Manifest artifact created

TEST 2: Checkpoint Creation
✓ Checkpoint created
✓ Checkpoint validated
✓ Resume plan generated

TEST 3: Artifact Handoff
✓ Manifest loaded
✓ Research artifact created
✓ Planner loaded research artifact

TEST 4: Logging & Observability
✓ Events logged
✓ Log summary generated

✅ ALL TESTS PASSED
```

---

## Setup Instructions

### Prerequisites

1. **Python 3.8+** installed
2. **Claude Code** with autonomous-dev plugin
3. **PROJECT.md** exists at `.claude/PROJECT.md`

### Step 1: Verify Installation

```bash
cd /path/to/autonomous-dev

# Check that lib/ directory exists
ls plugins/autonomous-dev/lib/

# Should see:
# artifacts.py
# checkpoint.py
# logging_utils.py
# orchestrator.py
# test_framework.py
# test_workflow_v2.py
```

### Step 2: Create PROJECT.md

If you don't have `.claude/PROJECT.md`, create one:

```bash
cat > .claude/PROJECT.md << 'EOF'
# Project Context

## GOALS

1. Improve security
2. Automate workflows
3. Maintain code quality

## SCOPE

### In Scope
- Authentication features
- Testing automation
- Security scanning

### Out of Scope
- Social media integration
- Real-time chat
- Mobile apps

## CONSTRAINTS

- Must use Python 3.8+
- No third-party authentication frameworks
- 80% test coverage minimum
- All changes require code review
EOF
```

### Step 3: Test the Infrastructure

```bash
# Test orchestrator
python plugins/autonomous-dev/lib/orchestrator.py

# Test artifacts
python plugins/autonomous-dev/lib/artifacts.py

# Test checkpoints
python plugins/autonomous-dev/lib/checkpoint.py

# Test complete workflow
python plugins/autonomous-dev/lib/test_workflow_v2.py
```

All tests should pass! ✅

---

## Using v2.0 Components

### Example 1: Validate Alignment

```python
#!/usr/bin/env python3
from pathlib import Path
from plugins.autonomous_dev.lib.orchestrator import Orchestrator

# Initialize
orchestrator = Orchestrator(
    project_md_path=Path(".claude/PROJECT.md")
)

# Test requests
requests = [
    "implement user authentication with JWT",
    "add real-time chat functionality",
    "integrate OAuth with third-party auth"
]

for request in requests:
    success, message, workflow_id = orchestrator.start_workflow(request)
    print(f"\nRequest: {request}")
    if success:
        print(f"✅ ALIGNED: Workflow {workflow_id}")
    else:
        print(f"❌ BLOCKED")
        print(message[:200])  # First 200 chars
```

### Example 2: Create and Resume Workflow

```python
#!/usr/bin/env python3
from plugins.autonomous_dev.lib.artifacts import ArtifactManager, generate_workflow_id
from plugins.autonomous_dev.lib.checkpoint import CheckpointManager

# Create workflow
workflow_id = generate_workflow_id()
print(f"Created workflow: {workflow_id}")

artifact_manager = ArtifactManager()

# Create manifest
artifact_manager.create_manifest_artifact(
    workflow_id=workflow_id,
    request="implement feature X",
    alignment_data={'validated': True},
    workflow_plan={'agents': ['researcher', 'planner']}
)

# Simulate researcher completing
artifact_manager.write_artifact(
    workflow_id=workflow_id,
    artifact_type='research',
    data={
        'version': '2.0',
        'agent': 'researcher',
        'workflow_id': workflow_id,
        'status': 'completed',
        'codebase_patterns': [],
        'best_practices': []
    }
)

# Create checkpoint
checkpoint_manager = CheckpointManager()
checkpoint_manager.create_checkpoint(
    workflow_id=workflow_id,
    completed_agents=['orchestrator', 'researcher'],
    current_agent='planner',
    artifacts_created=['manifest.json', 'research.json']
)

print("Checkpoint created!")

# Later: Resume
resumable = checkpoint_manager.list_resumable_workflows()
print(f"\nResumable workflows: {len(resumable)}")

if resumable:
    plan = checkpoint_manager.get_resume_plan(workflow_id)
    print(f"Progress: {plan['progress_percentage']}%")
    print(f"Next agent: {plan['next_agent']}")
```

### Example 3: Use Logging

```python
#!/usr/bin/env python3
from plugins.autonomous_dev.lib.logging_utils import WorkflowLogger

logger = WorkflowLogger(
    workflow_id="test_20251023",
    agent_name="my_agent"
)

# Log events
logger.log_event('agent_start', 'Agent started')

# Log decisions
logger.log_decision(
    decision='Use library X',
    rationale='Best performance for our use case',
    alternatives_considered=['library Y', 'library Z']
)

# Log alignment
logger.log_alignment_check(
    is_aligned=True,
    reason='Feature aligns with security goals'
)

# Get summary
summary = logger.get_log_summary()
print(f"Total events: {summary['total_events']}")
print(f"Decisions: {len(summary['decisions'])}")
```

---

## What's NOT Working Yet

### Agent Invocation ⏳

**Current state**: Infrastructure ready, but actual agent invocation via Task tool not yet implemented.

**What this means**:
- ✅ You can create workflows
- ✅ You can validate alignment
- ✅ You can create artifacts manually
- ❌ Orchestrator can't invoke actual agents yet

**Timeline**: Week 4+ (agent integration in progress)

### Full Pipeline ⏳

**Current state**: Each component works in isolation, but the complete 8-agent pipeline isn't connected yet.

**What this means**:
- ✅ Orchestrator → manifest.json works
- ✅ You can manually create research.json, architecture.json, etc.
- ❌ Orchestrator doesn't automatically invoke researcher → planner → etc.

**Timeline**: Weeks 4-10 (sequential pipeline, then parallel validators)

---

## Command Interface (Coming Soon)

The `/auto-implement-v2` command is **specified but not yet functional**:

```bash
# FUTURE (Week 4+):
/auto-implement-v2 implement user authentication

# Will do:
# 1. Validate alignment with PROJECT.md
# 2. Create workflow + artifacts
# 3. Invoke 8-agent pipeline
# 4. Generate production-ready code
# 5. Create commit
```

**Current workaround**: Use the Python API directly (see examples above)

---

## Architecture Overview

```
┌─────────────────────────────────────┐
│      YOUR REQUEST                   │
│  "implement user authentication"    │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  HOOKS ✅ (Working)                 │
│  - Detect implementation keywords   │
│  - Block sensitive files            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  ORCHESTRATOR ✅ (Working)          │
│  1. Parse PROJECT.md                │
│  2. Validate alignment              │
│  3. Create workflow                 │
│  4. Initialize artifacts            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  AGENT PIPELINE ⏳ (Week 4+)        │
│  researcher → planner → test-master │
│  → implementer → validators         │
└─────────────────────────────────────┘
```

**Green = Working**, **Yellow = In Progress**

---

## Troubleshooting

### "PROJECT.md not found"

```bash
# Create PROJECT.md
cat > .claude/PROJECT.md << 'EOF'
# Project Context

## GOALS
- Your goals here

## SCOPE
### In Scope
- Your scope here

## CONSTRAINTS
- Your constraints here
EOF
```

### "ModuleNotFoundError"

```bash
# Make sure you're in the project root
cd /path/to/autonomous-dev

# Run with correct Python path
python plugins/autonomous-dev/lib/orchestrator.py
```

### "FileNotFoundError: .claude/artifacts"

Directories are created automatically when you run the orchestrator. But you can create them manually:

```bash
mkdir -p .claude/artifacts
mkdir -p .claude/logs/workflows
```

### Tests fail on alignment

Make sure your PROJECT.md has GOALS, SCOPE, and CONSTRAINTS sections with actual content (not just empty headers).

---

## Next Steps

### For Users (Week 4+)

Once agent invocation is complete:

```bash
# Install v2.0 plugin
/plugin install autonomous-dev@v2.0

# Use autonomous implementation
/auto-implement-v2 implement user authentication

# Resume interrupted workflows
/auto-implement-v2 --resume 20251023_123456
```

### For Developers (Now)

Contribute to v2.0 development:

1. **Test the infrastructure**
   ```bash
   python plugins/autonomous-dev/lib/test_workflow_v2.py
   ```

2. **Explore the code**
   ```bash
   # Read the modules
   cat plugins/autonomous-dev/lib/orchestrator.py
   cat plugins/autonomous-dev/lib/artifacts.py
   cat plugins/autonomous-dev/lib/checkpoint.py
   ```

3. **Try the examples**
   - See "Using v2.0 Components" section above

4. **Review the documentation**
   - `docs/V2_IMPLEMENTATION_STATUS.md` - Complete status
   - `docs/WEEK1_VALIDATION.md` - Foundation
   - `docs/WEEK2_VALIDATION.md` - Orchestrator
   - `docs/WEEK3_VALIDATION.md` - Pipeline

---

## Resources

### Documentation

- **Implementation Status**: `docs/V2_IMPLEMENTATION_STATUS.md` (850 lines)
- **Specification**: `AUTONOMOUS_DEV_V2_MASTER_SPEC.md` (171KB)
- **Validation Reports**: `docs/WEEK{1,2,3}_VALIDATION.md`
- **Library Docs**: `plugins/autonomous-dev/lib/README.md`

### Key Files

- **Orchestrator**: `plugins/autonomous-dev/lib/orchestrator.py`
- **Artifacts**: `plugins/autonomous-dev/lib/artifacts.py`
- **Checkpoints**: `plugins/autonomous-dev/lib/checkpoint.py`
- **Tests**: `plugins/autonomous-dev/lib/test_workflow_v2.py`

### Architecture

- **Dogfooding**: `docs/DOGFOODING-ARCHITECTURE.md`
- **Root vs Plugin**: `docs/ROOT-VS-PLUGIN-ARCHITECTURE.md`

---

## FAQ

### Q: Can I use v2.0 in production?

**A**: Not yet. Infrastructure is complete and tested, but agent invocation is still in development (Week 4+). Current ETA: 8-10 weeks for beta.

### Q: Should I migrate from v1.x?

**A**: No, keep using v1.x for production work. v2.0 is for testing and development only right now.

### Q: What's the timeline for full v2.0?

**A**:
- ✅ Weeks 1-3: Infrastructure (DONE)
- ⏳ Weeks 4-5: Agent invocation
- ⏳ Weeks 6-7: Sequential pipeline
- ⏳ Weeks 8-10: Parallel validators
- ⏳ Weeks 11-12: Polish & beta

### Q: How can I help?

**A**: Test the infrastructure! Run the examples, try the API, report any issues. Feedback is valuable even at this early stage.

### Q: What's different from v1.x?

**A**: See `docs/V2_IMPLEMENTATION_STATUS.md` section "Key Design Decisions" for detailed comparison.

---

## Summary

**v2.0 Status**: 🟢 **Infrastructure Complete** (Weeks 1-3)

**What works**:
- ✅ PROJECT.md parsing & validation
- ✅ Semantic alignment checking
- ✅ Artifact creation & handoff
- ✅ Checkpoint/resume system
- ✅ Comprehensive logging

**What's next**:
- ⏳ Agent invocation (Week 4+)
- ⏳ Full pipeline (Weeks 6-10)
- ⏳ Production ready (Week 12)

**Try it now**:
```bash
python plugins/autonomous-dev/lib/test_workflow_v2.py
```

---

**Status**: Infrastructure Ready for Testing
**Version**: 2.0.0-alpha
**Last Updated**: 2025-10-23
