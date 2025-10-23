---
name: auto-implement-v2
description: Autonomous implementation v2.0 with PROJECT.md-first governance and 8-agent orchestrated pipeline
examples:
  - /auto-implement-v2 user authentication with JWT tokens
  - /auto-implement-v2 --resume 20251023_093456
---

# Autonomous Implementation v2.0

**Version**: 2.0.0-alpha
**Status**: Week 3 implementation

Fully autonomous, PROJECT.md-aligned feature implementation using orchestrated 8-agent pipeline.

## What This Command Does

Coordinates 8 specialized agents to autonomously implement features:

1. **Orchestrator**: Validates PROJECT.md alignment
2. **Researcher**: Finds patterns and best practices
3. **Planner**: Designs architecture
4. **Test-Master**: Writes failing tests (TDD red phase)
5. **Implementer**: Makes tests pass (TDD green phase)
6. **Reviewer**: Validates code quality
7. **Security-Auditor**: Scans for vulnerabilities
8. **Doc-Master**: Updates documentation

## Prerequisites

1. **PROJECT.md must exist** at `.claude/PROJECT.md`
2. Must contain: GOALS, SCOPE, CONSTRAINTS sections

**If PROJECT.md missing**:
```bash
# Create template
cat > .claude/PROJECT.md << 'EOF'
# Project Context

## GOALS
- [Your primary objective]
- [Success metrics]

## SCOPE

### In Scope
- [Features you're building]

### Out of Scope
- [Features to avoid]

## CONSTRAINTS
- [Technical constraints]
- [Business constraints]
EOF

# Edit with your actual goals
vim .claude/PROJECT.md
```

## Usage

### Start New Workflow

```bash
/auto-implement-v2 implement user authentication with JWT tokens
```

**What happens**:
1. ✓ Validates alignment with PROJECT.md
2. ✓ Creates workflow artifacts
3. ✓ Invokes 8-agent pipeline
4. ✓ Generates production-ready code
5. ✓ Creates commit with full context

**Duration**: 60-120 seconds

### Resume Interrupted Workflow

```bash
# List resumable workflows
/auto-implement-v2 --list

# Resume specific workflow
/auto-implement-v2 --resume 20251023_093456
```

## Step-by-Step Execution

### Step 1: Initialize Orchestrator

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from orchestrator import Orchestrator
from checkpoint import CheckpointManager

# Get user request from command args
request = ' '.join(sys.argv[1:])

# Check for resume flag
if '--resume' in request:
    workflow_id = request.split('--resume')[1].strip()
    print(f"📂 Resuming workflow: {workflow_id}")
    # TODO: Implement resume logic
    sys.exit(0)

if '--list' in request:
    checkpoint_manager = CheckpointManager()
    resumable = checkpoint_manager.list_resumable_workflows()

    print("📋 Resumable Workflows:\n")
    if not resumable:
        print("  No resumable workflows found.")
    else:
        for wf in resumable:
            print(f"  • {wf['workflow_id']}")
            print(f"    Progress: {wf['progress']}")
            print(f"    Next: {wf['current_agent']}")
            print(f"    Created: {wf['created_at']}\n")

    sys.exit(0)

# Initialize orchestrator
try:
    orchestrator = Orchestrator()
except ValueError as e:
    print(f"❌ Error: {e}")
    print("\n💡 Create .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS")
    sys.exit(1)

# Start workflow
success, message, workflow_id = orchestrator.start_workflow(request)

print(message)

if not success:
    sys.exit(1)

# Workflow initialized - now invoke agent pipeline
print("\n" + "="*60)
print("AGENT PIPELINE")
print("="*60 + "\n")
```

### Step 2: Invoke Researcher

After workflow initialization, invoke the researcher agent:

**Prompt**:
```
You are the researcher agent for autonomous-dev v2.0.

Workflow ID: {workflow_id}

Read the workflow manifest:
.claude/artifacts/{workflow_id}/manifest.json

Your task:
1. Search codebase for existing patterns related to: {request}
2. Research best practices via WebSearch
3. Gather security considerations
4. Document recommended libraries
5. Provide alternatives considered

Use these tools:
- Read: Load manifest.json
- Grep: Search codebase patterns
- Glob: Find related files
- WebSearch: Find best practices
- WebFetch: Get detailed articles

Output artifact (JSON format):
.claude/artifacts/{workflow_id}/research.json

Required structure:
{
  "version": "2.0",
  "agent": "researcher",
  "workflow_id": "{workflow_id}",
  "status": "completed",
  "codebase_patterns": [
    {
      "pattern": "...",
      "location": "...",
      "relevance": "..."
    }
  ],
  "best_practices": [
    {
      "practice": "...",
      "source": "...",
      "rationale": "..."
    }
  ],
  "security_considerations": [...],
  "recommended_libraries": [...],
  "alternatives_considered": [...]
}

After completing research, write the artifact to the specified path.
```

### Step 3: Invoke Remaining Agents

**Pipeline order**:
```
orchestrator (done) → researcher → planner → test-master → implementer → [reviewer ‖ security ‖ docs]
```

**For each agent**:
1. Wait for previous agent to complete
2. Verify artifact was created
3. Invoke next agent with context
4. Create checkpoint after completion
5. Update progress tracker

### Step 4: Final Report

After all agents complete:

1. Read all artifacts
2. Generate final report
3. Create commit message
4. Execute commit (if requested)

## Artifacts Created

Each workflow creates:

```
.claude/artifacts/{workflow_id}/
├── manifest.json           # Orchestrator: Workflow plan
├── research.json          # Researcher: Patterns & best practices
├── architecture.json      # Planner: System design
├── test-plan.json        # Test-Master: Test suite
├── implementation.json    # Implementer: Code changes
├── review.json           # Reviewer: Quality check
├── security.json         # Security: Vulnerability scan
├── docs.json            # Doc-Master: Documentation updates
├── final-report.json    # Orchestrator: Aggregated results
├── checkpoint.json      # Checkpoint: Resume state
└── logs/
    ├── orchestrator.log
    ├── researcher.log
    ├── planner.log
    ├── test-master.log
    ├── implementer.log
    ├── reviewer.log
    ├── security-auditor.log
    └── doc-master.log
```

## Example Session

```bash
$ /auto-implement-v2 implement user authentication with JWT tokens

📋 Loading PROJECT.md...
✓ Found: .claude/PROJECT.md

🔍 Validating alignment...
✓ Aligns with goal: "Improve security"
✓ Within scope: "Authentication"
✓ Respects all 3 constraints

✅ **Workflow Started**

Workflow ID: 20251023_101530
Request: implement user authentication with JWT tokens

Alignment: ✓ Validated
- Goals: Improve security
- Scope: ✓ Within scope
- Constraints: ✓ All respected

============================================================
AGENT PIPELINE
============================================================

[1/8] 🔍 Researcher (10s)
  ✓ Searched codebase patterns
  ✓ Researched best practices
  ✓ Identified security considerations
  → research.json created

[2/8] 📐 Planner (15s)
  ✓ Designed architecture
  ✓ Defined API contracts
  ✓ Created implementation plan
  → architecture.json created

[3/8] ✍️  Test-Master (10s)
  ✓ Generated test suite
  ✓ Tests failing (red phase) ✓
  ✓ 80% coverage target
  → test-plan.json + tests/*.py created

[4/8] 💻 Implementer (30s)
  ✓ Implemented code
  ✓ Tests passing (green phase) ✓
  ✓ 85% coverage achieved
  → implementation.json + src/*.py created

[5-7/8] 🔄 Validators (parallel, 20s)
  [5/8] 👀 Reviewer: ✓ Quality approved
  [6/8] 🔒 Security: ✓ No issues found
  [7/8] 📚 Doc-Master: ✓ Docs updated

[8/8] ✅ Orchestrator: Final report
  → final-report.json created

============================================================
✨ WORKFLOW COMPLETE
============================================================

Duration: 95 seconds
Files changed: 5 files
Tests added: 15 tests
Coverage: 85%
Security issues: 0

📝 Commit message generated:
feat: implement user authentication with JWT tokens

Add JWT-based authentication system with secure token handling...

Would you like to:
1. Review implementation
2. Commit changes
3. Create pull request
```

## Error Handling

### Alignment Failure

```bash
❌ **Alignment Failed**

Your request: "add GraphQL API"

Issue: Request is explicitly out of scope in PROJECT.md

PROJECT.md excerpt:
OUT OF SCOPE:
- GraphQL API

To proceed:
1. Modify request to use REST API (in scope)
2. OR update PROJECT.md if direction changed
```

### Agent Failure

```bash
⚠️  Agent Failed: planner

Error: Timeout after 60 seconds

Checkpoint created: .claude/artifacts/20251023_101530/checkpoint.json

You can:
1. Resume: /auto-implement-v2 --resume 20251023_101530
2. Review logs: cat .claude/artifacts/20251023_101530/logs/planner.log
```

## Comparison: v1.x vs v2.0

**v1.x**:
- ❌ Opaque Python scripts
- ❌ Session files (not structured)
- ❌ Hard to debug
- ❌ No artifact validation

**v2.0**:
- ✅ Transparent markdown agents
- ✅ Structured JSON artifacts
- ✅ Complete audit trail
- ✅ Schema validation
- ✅ Checkpoint/resume
- ✅ Semantic alignment

## Configuration

No configuration required - uses PROJECT.md as single source of truth.

**Optional**: Set model preferences in agent definitions
- Orchestrator: sonnet (balanced)
- Planner: opus (complex reasoning)
- Security/Docs: haiku (fast)

## Troubleshooting

**"PROJECT.md not found"**:
```bash
# Create from template
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

**"Workflow stuck"**:
```bash
# Check progress
cat .claude/artifacts/{workflow_id}/progress.json

# Check logs
cat .claude/artifacts/{workflow_id}/logs/*.log

# Resume if interrupted
/auto-implement-v2 --resume {workflow_id}
```

**"Agent failed"**:
```bash
# Checkpoints created automatically
# Resume will retry failed agent
/auto-implement-v2 --resume {workflow_id}
```

## Success Criteria

✅ 100% PROJECT.md alignment (zero drift)
✅ 80%+ test coverage
✅ 0 critical security issues
✅ Documentation updated
✅ Complete audit trail

## References

- **Spec**: AUTONOMOUS_DEV_V2_MASTER_SPEC.md
- **Week 1**: docs/WEEK1_VALIDATION.md (Foundation)
- **Week 2**: docs/WEEK2_VALIDATION.md (Orchestrator)
- **Architecture**: docs/DOGFOODING-ARCHITECTURE.md

---

**Status**: Week 3 implementation in progress
**Next**: Connect to actual agent invocation via Task tool
