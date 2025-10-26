# Agent Communication Verification Guide

## Overview

The `test_agent_communication.py` script provides programmatic verification that:
1. **Agents are executing** (not just queued)
2. **Inter-agent communication is working** (agents read each other's outputs)
3. **Skills are being used** (agents reference skill patterns in their outputs)

Instead of manually watching agent execution, run this script to get concrete proof.

## Quick Start

### Step 1: Trigger agent execution in Claude Code

Run this command in your Claude Code session:
```
/auto-implement "add user authentication"
```

Wait for the workflow to complete. You'll see:
- ✓ Workflow initialized
- Agents executing...
- ✓ Workflow complete

### Step 2: Verify agent execution and communication

Once workflow is complete, run:
```bash
python3 tests/test_agent_communication.py
```

This will:
- Find the latest workflow in `.claude/artifacts/`
- Generate a comprehensive verification report
- Exit with status 0 (success - all agents executed) or 1 (incomplete)

## What Gets Verified

### 1. Agent Execution Verification
Checks if each agent's output file exists:
- ✅ `research.json` - researcher agent
- ✅ `architecture.json` - planner agent
- ✅ `tests.json` - test-master agent
- ✅ `implementation.json` - implementer agent
- ✅ `review.json` - reviewer agent
- ✅ `security.json` - security-auditor agent
- ✅ `documentation.md` - doc-master agent

**What it proves**: Agents actually ran and saved outputs (not just queued)

### 2. Inter-Agent Communication Verification
Checks if agents reference each other's outputs:

**Communication Chain 1**: Planner → Researcher
- Looks for: "research", "researcher", "pattern", "best practice" in planner output
- Proves: Planner read and incorporated researcher findings

**Communication Chain 2**: Implementer → Planner
- Looks for: "architecture", "design", "planner", "pattern" in implementer output
- Proves: Implementer read and followed planner's design

**Communication Chain 3**: Test-Master → Planner
- Looks for: "architecture", "design", "interface", "contract" in test-master output
- Proves: Test-Master understood and validated against planner's design

**What it proves**: Agents are reading and building upon each other's work

### 3. Skill Usage Verification
Checks if agents reference skill-specific patterns:

**Python Standards** (in implementer output):
- Indicators: "type hint", "docstring", "pep 8", "black", "isort"
- Proves: Implementer followed python-standards skill

**Testing Guide** (in test-master output):
- Indicators: "pytest", "unit test", "integration test", "coverage", "mock", "fixture", "assert"
- Proves: Test-Master followed testing-guide skill

**Security Patterns** (in security-auditor output):
- Indicators: "injection", "xss", "csrf", "authentication", "authorization", "validation", "sanitize"
- Proves: Security-Auditor applied security-patterns skill

**Documentation Guide** (in doc-master output):
- Indicators: "##", "###", "example", "usage", "api", "parameter", "return"
- Proves: Doc-Master followed documentation-guide skill

**What it proves**: Agents are using skills for consistency and best practices

## Example Output

```
======================================================================
COMPLETE AGENT VERIFICATION REPORT
======================================================================
Workflow ID: 20251026_213955
Timestamp: 1730000000.0

======================================================================
AGENT EXECUTION VERIFICATION
======================================================================
Workflow ID: 20251026_213955

Artifacts found: 7
  - research.json
  - architecture.json
  - tests.json
  - implementation.json
  - review.json
  - security.json
  - documentation.md

  ✓ researcher: research.json (2548 bytes)
  ✓ planner: architecture.json (3891 bytes)
  ✓ test-master: tests.json (4125 bytes)
  ✓ implementer: implementation.json (5672 bytes)
  ✓ reviewer: review.json (2143 bytes)
  ✓ security-auditor: security.json (1987 bytes)
  ✓ doc-master: documentation.md (3456 bytes)

======================================================================
INTER-AGENT COMMUNICATION VERIFICATION
======================================================================

1. Checking: Planner → Researcher communication
  ✓ Planner references researcher findings

2. Checking: Implementer → Planner communication
  ✓ Implementer references planner design

3. Checking: Test-Master → Planner communication
  ✓ Test-Master references planner design

======================================================================
SKILL USAGE VERIFICATION
======================================================================

1. Checking: Implementer uses python-standards skill
  ✓ Found Python standards references: type hint, docstring, pep 8

2. Checking: Test-Master uses testing-guide skill
  ✓ Found testing skill references: pytest, unit test, coverage, mock

3. Checking: Security-Auditor uses security-patterns skill
  ✓ Found security skill references: injection, xss, csrf, authentication

4. Checking: Doc-Master uses documentation-guide skill
  ✓ Found documentation skill references: ##, ###, example, usage, api

======================================================================
VERIFICATION SUMMARY
======================================================================

1. AGENT EXECUTION
   Status: ✅ VERIFIED
   Agents executed: 7/7

2. INTER-AGENT COMMUNICATION
   Status: ✅ VERIFIED
   Communication chains found: 3
   ✓ researcher→planner
   ✓ planner→implementer
   ✓ planner→test-master

3. SKILL USAGE
   Status: ✅ VERIFIED
   Skills used: 4
   ✓ python-standards
     Indicators: type hint, docstring, pep 8...
   ✓ testing-guide
     Indicators: pytest, unit test, coverage...
   ✓ security-patterns
     Indicators: injection, xss, csrf...
   ✓ documentation-guide
     Indicators: ##, ###, example...

======================================================================
✅ ALL VERIFICATIONS PASSED

Conclusion:
- Agents are executing (not just queued)
- Inter-agent communication is working
- Skills are being used by agents
======================================================================
```

## Running Against Specific Workflow

If you want to verify a specific workflow (not the latest):

```python
from tests.test_agent_communication import AgentCommunicationVerifier

verifier = AgentCommunicationVerifier()
report = verifier.generate_verification_report("20251026_213955")
```

## Interpreting Results

### ✅ ALL VERIFICATIONS PASSED
- All agents executed and created output files
- Agents are reading and incorporating each other's work
- Agents are actively using skills in their outputs
- **Conclusion**: Autonomous workflow is functioning correctly

### ⚠️ SOME VERIFICATIONS INCOMPLETE
This could mean:
- **Agents haven't executed yet** - Still queued in Task tool framework
- **Agent outputs haven't been saved** - Infrastructure issue
- **Communication is working but not visible** - Agents producing outputs but not explicitly referencing previous work
- **Skills not detected** - Agents using skills but not in identifiable patterns

**Next steps if incomplete**:
1. Check `.claude/artifacts/[workflow_id]/` directory exists
2. Verify files were created with `ls -la .claude/artifacts/[workflow_id]/`
3. Check file sizes - empty files might indicate errors
4. Review agent logs in `.claude/logs/workflows/[workflow_id]/`

## Troubleshooting

### No workflows found
```
❌ No artifacts directory found
```
- Run `/auto-implement "test feature"` first to create a workflow
- Ensure it completes before running verification

### Missing agent artifacts
```
❌ researcher: research.json NOT FOUND
```
- That agent may have failed
- Check logs: `.claude/logs/workflows/[workflow_id]/researcher.log`

### No inter-agent communication detected
```
⚠️  Implementer doesn't reference planner output
```
- Agent executed but outputs may be in different format
- Check artifact content manually: `cat .claude/artifacts/[workflow_id]/implementation.json`

### No skill indicators found
```
⚠️  No Python standards skill indicators found
```
- Agent completed but didn't reference skill patterns in output
- This might be OK - agent used skill but didn't explicitly mention it
- Manually review the artifact file to verify quality

## When to Use This

✅ **Use this verification when**:
- You want proof that agents are actually executing (not just queued)
- You need to validate inter-agent communication is working
- You're troubleshooting why agents aren't producing expected outputs
- You want to demonstrate the autonomous workflow is functional

❌ **Don't use this for**:
- Real-time progress monitoring (it checks completed artifacts)
- Individual test output (use pytest for that)
- Code quality checks (use reviewer agent output instead)

## Related Files

- **Implementation**: `plugins/autonomous-dev/lib/workflow_coordinator.py`
- **Test File**: `tests/test_agent_communication.py`
- **Agent Configs**: `plugins/autonomous-dev/lib/agent_invoker.py`
- **Artifact Management**: `plugins/autonomous-dev/lib/artifacts.py`
- **Logs**: `.claude/logs/workflows/[workflow_id]/`

## See Also

- `/auto-implement` command documentation
- Agent routing implementation details in `docs/IMPLEMENTATION_COMPLETE_2025-10-27.md`
- Project philosophy in `.claude/PROJECT.md`
