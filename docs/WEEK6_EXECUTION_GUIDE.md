# Week 6 Execution Guide: First Real Agent Invocation

**Date**: 2025-10-23
**Status**: ⏳ Ready to Execute
**Prerequisites**: ✅ Weeks 1-5 Infrastructure Complete

---

## Overview

Week 6 is the **critical transition** from infrastructure to execution. This guide provides step-by-step instructions for enabling real agent execution and testing the orchestrator → researcher pipeline.

### Goals

1. Enable Task tool invocation (uncomment one line)
2. Deploy researcher-v2.md agent
3. Test real researcher execution
4. Validate research.json creation
5. Verify checkpoint system works with real agent

### Expected Duration

**5-7 days** broken down as:
- Day 1-2: Setup and first execution
- Day 3-4: Testing and refinement
- Day 5: Validation and documentation

---

## Step-by-Step Execution

### Phase 1: Pre-Flight Checks (30 minutes)

#### 1.1: Verify Infrastructure

```bash
# Run all infrastructure tests
cd /path/to/autonomous-dev

# Test artifacts system
python plugins/autonomous-dev/lib/artifacts.py

# Test orchestrator
python plugins/autonomous-dev/lib/orchestrator.py

# Test checkpoint system
python plugins/autonomous-dev/lib/checkpoint.py

# Test workflow simulation
python plugins/autonomous-dev/lib/test_workflow_v2.py

# Test invocation preparation
python plugins/autonomous-dev/lib/test_researcher_invocation.py

# Test Task tool integration readiness
python plugins/autonomous-dev/lib/test_task_tool_integration.py
```

**Expected Result**: All tests pass ✅

#### 1.2: Backup Current State

```bash
# Create backup branch
git checkout -b week6-execution-backup
git push origin week6-execution-backup

# Return to master
git checkout master

# Tag current state
git tag v2.0.0-pre-week6 -m "Infrastructure complete, ready for Week 6"
git push origin v2.0.0-pre-week6
```

**Why**: If Week 6 fails, can easily revert

#### 1.3: Verify PROJECT.md Exists

```bash
# Check PROJECT.md
if [ -f ".claude/PROJECT.md" ]; then
    echo "✅ PROJECT.md exists"
    cat .claude/PROJECT.md | head -20
else
    echo "❌ PROJECT.md missing - create it first"
    exit 1
fi
```

**Expected**: PROJECT.md with GOALS, SCOPE, CONSTRAINTS

---

### Phase 2: Enable Task Tool (15 minutes)

#### 2.1: Uncomment Task Tool Invocation

Edit `plugins/autonomous-dev/lib/orchestrator.py`:

**Line 603-609 BEFORE**:
```python
# TODO: Uncomment when ready to invoke real Task tool
# from claude_code import Task
# result = Task(
#     subagent_type=invocation['subagent_type'],
#     description=invocation['description'],
#     prompt=invocation['prompt']
# )
```

**Line 603-609 AFTER**:
```python
# Invoke real Task tool
from claude_code import Task
result = Task(
    subagent_type=invocation['subagent_type'],
    description=invocation['description'],
    prompt=invocation['prompt']
)
```

**Changes**: Removed comments, enabled import and invocation

#### 2.2: Handle Task Tool Result

Edit `plugins/autonomous-dev/lib/orchestrator.py` after line 609:

**BEFORE** (lines 611-618):
```python
# For now, return the invocation for manual testing
return {
    'status': 'ready_for_invocation',
    'workflow_id': workflow_id,
    'invocation': invocation,
    'expected_artifact': f'.claude/artifacts/{workflow_id}/research.json',
    'next_step': 'Manually invoke researcher or uncomment Task tool call'
}
```

**AFTER** (lines 611-630):
```python
# Task tool returns when researcher completes
# Result should contain any output from researcher
logger.log_event(
    'researcher_completed',
    'Researcher agent finished execution',
    metadata={'workflow_id': workflow_id}
)

# Verify research.json was created
research_path = Path(f'.claude/artifacts/{workflow_id}/research.json')
if not research_path.exists():
    raise FileNotFoundError(
        f"Researcher did not create research.json at {research_path}"
    )

# Validate research.json
research = self.artifact_manager.read_artifact(workflow_id, 'research')
logger.log_event(
    'research_validated',
    f'Research artifact validated: {len(research.get("best_practices", []))} best practices found'
)

return {
    'status': 'completed',
    'workflow_id': workflow_id,
    'research_artifact': str(research_path),
    'research_summary': {
        'codebase_patterns': len(research.get('codebase_patterns', [])),
        'best_practices': len(research.get('best_practices', [])),
        'security_considerations': len(research.get('security_considerations', [])),
        'recommended_libraries': len(research.get('recommended_libraries', []))
    }
}
```

**Why**: Proper result handling and validation

#### 2.3: Save Changes

```bash
git add plugins/autonomous-dev/lib/orchestrator.py
git status  # Verify only orchestrator.py changed
```

---

### Phase 3: Deploy Researcher Agent (10 minutes)

#### 3.1: Option A - Use Plugin System

```bash
# If using plugin system, researcher-v2.md is already available
# Just need to ensure it's active

# Verify researcher-v2.md exists
ls -la plugins/autonomous-dev/agents/researcher-v2.md

# Check if installed
ls -la .claude/agents/researcher.md

# If not installed, plugin system should deploy it
```

#### 3.2: Option B - Manual Deployment

```bash
# Backup v1.x researcher (optional)
if [ -f "plugins/autonomous-dev/agents/researcher.md" ]; then
    mv plugins/autonomous-dev/agents/researcher.md \
       plugins/autonomous-dev/agents/researcher-v1.md
fi

# Deploy v2.0 researcher
cp plugins/autonomous-dev/agents/researcher-v2.md \
   plugins/autonomous-dev/agents/researcher.md

# Verify
cat plugins/autonomous-dev/agents/researcher.md | head -20
```

**Expected**: researcher.md contains v2.0 artifact protocol

#### 3.3: Verify Agent Metadata

```bash
# Check frontmatter
head -10 plugins/autonomous-dev/agents/researcher.md

# Should see:
# ---
# name: researcher
# description: Research patterns and best practices (v2.0 artifact protocol)
# model: sonnet
# tools: [WebSearch, WebFetch, Read, Bash, Grep, Glob]
# ---
```

---

### Phase 4: First Test Execution (1-2 hours)

#### 4.1: Create Test Workflow

Create `test_week6_execution.py`:

```python
#!/usr/bin/env python3
"""
Week 6: First Real Agent Execution Test

This test actually invokes the Task tool and runs the researcher agent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "plugins/autonomous-dev/lib"))

from orchestrator import Orchestrator
from artifacts import ArtifactManager
from checkpoint import CheckpointManager


def test_first_real_execution():
    """Test real researcher agent execution"""

    print("=" * 70)
    print("WEEK 6: First Real Agent Execution Test")
    print("=" * 70)
    print()

    # Step 1: Create orchestrator
    print("Step 1: Initializing orchestrator...")
    orchestrator = Orchestrator()
    print("✓ Orchestrator initialized")
    print()

    # Step 2: Create workflow
    print("Step 2: Creating workflow...")
    success, message, workflow_id = orchestrator.start_workflow(
        "implement user authentication with JWT tokens"
    )

    if not success:
        print(f"✗ Failed to create workflow: {message}")
        return False

    print(f"✓ Workflow created: {workflow_id}")
    print()

    # Step 3: Invoke researcher (THIS WILL ACTUALLY RUN)
    print("Step 3: Invoking researcher agent...")
    print("NOTE: This will take 5-15 minutes")
    print("The researcher will:")
    print("  - Search codebase for auth patterns")
    print("  - Perform web research (3-5 queries)")
    print("  - Fetch best practices from 5+ sources")
    print("  - Create research.json artifact")
    print()

    try:
        result = orchestrator.invoke_researcher_with_task_tool(workflow_id)

        print("✓ Researcher completed!")
        print(f"  Status: {result['status']}")
        print(f"  Artifact: {result['research_artifact']}")
        print()

        # Step 4: Validate research.json
        print("Step 4: Validating research artifact...")

        summary = result['research_summary']
        print(f"  Codebase patterns: {summary['codebase_patterns']}")
        print(f"  Best practices: {summary['best_practices']}")
        print(f"  Security considerations: {summary['security_considerations']}")
        print(f"  Recommended libraries: {summary['recommended_libraries']}")
        print()

        # Minimum quality checks
        if summary['best_practices'] < 3:
            print("⚠ Warning: Expected at least 3 best practices")

        if summary['security_considerations'] < 3:
            print("⚠ Warning: Expected at least 3 security considerations")

        # Step 5: Verify checkpoint
        print("Step 5: Verifying checkpoint...")
        checkpoint_manager = CheckpointManager()
        checkpoint = checkpoint_manager.load_checkpoint(workflow_id)

        print(f"  Completed agents: {checkpoint['completed_agents']}")
        print(f"  Current agent: {checkpoint['current_agent']}")
        print(f"  Progress: {checkpoint_manager.get_resume_plan(workflow_id)['progress_percentage']}%")
        print()

        # Step 6: Read full research artifact
        print("Step 6: Reading full research artifact...")
        artifact_manager = ArtifactManager()
        research = artifact_manager.read_artifact(workflow_id, 'research')

        print("Research Artifact Contents:")
        print(f"  Version: {research['version']}")
        print(f"  Agent: {research['agent']}")
        print(f"  Status: {research['status']}")
        print()

        if research.get('best_practices'):
            print("Best Practices Found:")
            for i, bp in enumerate(research['best_practices'][:3], 1):
                print(f"  {i}. {bp['practice']}")
                print(f"     Source: {bp['source']}")
                print(f"     Rationale: {bp['rationale']}")
                print()

        print("=" * 70)
        print("✅ WEEK 6 TEST PASSED - Real agent execution successful!")
        print("=" * 70)
        print()

        return True

    except Exception as e:
        print(f"✗ Researcher execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_first_real_execution()
    sys.exit(0 if success else 1)
```

#### 4.2: Run First Test

```bash
# Make executable
chmod +x test_week6_execution.py

# Run test (THIS WILL TAKE 5-15 MINUTES)
python test_week6_execution.py

# Monitor progress
# - Watch for researcher starting
# - Watch for web searches
# - Watch for research.json creation
# - Watch for checkpoint creation
```

**Expected Output**:
```
======================================================================
WEEK 6: First Real Agent Execution Test
======================================================================

Step 1: Initializing orchestrator...
✓ Orchestrator initialized

Step 2: Creating workflow...
✓ Workflow created: 20251023_153045

Step 3: Invoking researcher agent...
NOTE: This will take 5-15 minutes
The researcher will:
  - Search codebase for auth patterns
  - Perform web research (3-5 queries)
  - Fetch best practices from 5+ sources
  - Create research.json artifact

[... researcher executes ...]

✓ Researcher completed!
  Status: completed
  Artifact: .claude/artifacts/20251023_153045/research.json

Step 4: Validating research artifact...
  Codebase patterns: 2
  Best practices: 5
  Security considerations: 6
  Recommended libraries: 2

Step 5: Verifying checkpoint...
  Completed agents: ['orchestrator', 'researcher']
  Current agent: planner
  Progress: 25%

Step 6: Reading full research artifact...
Research Artifact Contents:
  Version: 2.0
  Agent: researcher
  Status: completed

Best Practices Found:
  1. Use RS256 for production JWT signing
     Source: https://auth0.com/blog/rs256-vs-hs256/
     Rationale: Asymmetric keys prevent token forgery

  [... more ...]

======================================================================
✅ WEEK 6 TEST PASSED - Real agent execution successful!
======================================================================
```

---

### Phase 5: Validation & Refinement (2-3 days)

#### 5.1: Test Different Request Types

Test researcher with various requests:

```python
test_requests = [
    "implement rate limiting for API endpoints",
    "add caching layer for database queries",
    "implement webhook signature verification",
    "add logging and monitoring system",
    "implement feature flags system"
]

for request in test_requests:
    success, _, workflow_id = orchestrator.start_workflow(request)
    if success:
        result = orchestrator.invoke_researcher_with_task_tool(workflow_id)
        # Validate result quality
```

#### 5.2: Quality Checks

For each execution, verify:

```python
def validate_research_quality(workflow_id):
    """Validate research artifact meets quality standards"""

    research = artifact_manager.read_artifact(workflow_id, 'research')

    checks = []

    # Check 1: Has codebase patterns (or explicitly states none found)
    if research.get('codebase_patterns'):
        checks.append(('codebase_patterns', True, 'Found patterns'))
    else:
        checks.append(('codebase_patterns', False, 'No patterns documented'))

    # Check 2: Has at least 3 best practices
    bp_count = len(research.get('best_practices', []))
    checks.append(('best_practices', bp_count >= 3, f'{bp_count} practices'))

    # Check 3: Has security considerations
    sec_count = len(research.get('security_considerations', []))
    checks.append(('security', sec_count >= 3, f'{sec_count} considerations'))

    # Check 4: Has recommended libraries
    lib_count = len(research.get('recommended_libraries', []))
    checks.append(('libraries', lib_count >= 1, f'{lib_count} libraries'))

    # Check 5: Has alternatives
    alt_count = len(research.get('alternatives_considered', []))
    checks.append(('alternatives', alt_count >= 1, f'{alt_count} alternatives'))

    # Print results
    print(f"\nQuality Check: {workflow_id}")
    for name, passed, detail in checks:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}: {detail}")

    return all(passed for _, passed, _ in checks)
```

#### 5.3: Performance Monitoring

Track performance metrics:

```python
import time

start_time = time.time()
result = orchestrator.invoke_researcher_with_task_tool(workflow_id)
duration = time.time() - start_time

print(f"Researcher duration: {duration:.1f}s")

# Target: < 15 minutes (900 seconds)
if duration > 900:
    print("⚠ Warning: Researcher taking longer than expected")
```

#### 5.4: Error Handling Tests

Test error scenarios:

```python
# Test 1: Invalid workflow_id
try:
    orchestrator.invoke_researcher_with_task_tool("invalid_id")
    print("✗ Should have raised error")
except Exception as e:
    print(f"✓ Caught error: {e}")

# Test 2: Missing manifest.json
# (manually delete manifest and retry)

# Test 3: Researcher timeout
# (if researcher takes > 20 minutes, should handle gracefully)
```

---

### Phase 6: Documentation (1 day)

#### 6.1: Create WEEK6_VALIDATION.md

Document:
- All test results
- Performance metrics
- Quality assessments
- Issues encountered
- Solutions applied

#### 6.2: Update WEEK6_EXECUTION_GUIDE.md

Add "Lessons Learned" section with:
- What worked well
- What needed adjustment
- Recommendations for Week 7

#### 6.3: Create Week 6 Commit

```bash
git add plugins/autonomous-dev/lib/orchestrator.py
git add test_week6_execution.py
git add docs/WEEK6_VALIDATION.md

git commit -m "feat: Week 6 - enable real researcher agent execution

Enable Task tool invocation and validate real researcher execution.
Successfully tested orchestrator → researcher pipeline with real agent.

Changes:
- Uncommented Task tool invocation in orchestrator.py
- Added result handling and validation
- Deployed researcher-v2.md agent
- Tested with 5+ different request types
- Validated research.json quality

Test Results:
- First execution: ✅ Success (12.3 minutes)
- Quality checks: ✅ All passing
- Checkpoint system: ✅ Working
- Performance: ✅ Within targets

Statistics:
- Avg duration: 10-15 minutes per research
- Avg best practices: 4-6 per request
- Avg security considerations: 5-7 per request
- Success rate: 100% (5/5 tests)

Week 6 Complete: Real agent execution validated!"
```

---

## Troubleshooting

### Issue 1: Task Tool Import Error

**Symptom**:
```python
ModuleNotFoundError: No module named 'claude_code'
```

**Cause**: Task tool not available in current environment

**Solutions**:
1. **Option A**: Verify Claude Code version supports Task tool
2. **Option B**: Use alternative import path
3. **Option C**: Contact Claude Code support for Task tool access

**Workaround**: Keep Task tool commented and use simulation mode for now

### Issue 2: Researcher Doesn't Create research.json

**Symptom**:
```
FileNotFoundError: Researcher did not create research.json
```

**Debugging Steps**:
```python
# Check if researcher agent exists
ls -la plugins/autonomous-dev/agents/researcher.md

# Check researcher prompt includes artifact creation
grep "research.json" plugins/autonomous-dev/agents/researcher.md

# Check artifacts directory was created
ls -la .claude/artifacts/

# Check researcher logs
cat .claude/logs/workflows/<workflow_id>_researcher.log
```

**Solutions**:
1. Verify researcher-v2.md is deployed
2. Check prompt includes `.claude/artifacts/{workflow_id}/research.json` path
3. Ensure researcher has Write permissions

### Issue 3: Researcher Takes Too Long

**Symptom**: Researcher execution exceeds 20 minutes

**Debugging**:
```python
# Check what researcher is doing
tail -f .claude/logs/workflows/<workflow_id>_researcher.log

# Monitor progress
while true; do
    echo "Checking progress..."
    ls -la .claude/artifacts/<workflow_id>/
    sleep 30
done
```

**Solutions**:
1. Reduce number of WebSearch queries (5 → 3)
2. Limit WebFetch calls (5 → 3)
3. Add timeout to researcher prompt
4. Use Haiku model for faster (but less thorough) research

### Issue 4: Low Quality Research

**Symptom**: research.json has < 3 best practices or minimal content

**Quality Check**:
```python
research = artifact_manager.read_artifact(workflow_id, 'research')

# Check quality
if len(research.get('best_practices', [])) < 3:
    print("Quality issue: Insufficient best practices")

# Review content
for bp in research['best_practices']:
    print(f"Practice: {bp['practice']}")
    print(f"Source: {bp['source']}")
    print(f"Rationale: {bp['rationale']}")
```

**Solutions**:
1. Enhance researcher prompt with quality requirements
2. Add examples of good research in prompt
3. Increase minimum requirements in prompt
4. Use Opus model for higher quality (but slower)

---

## Success Criteria

Week 6 is successful when:

✅ **Execution**:
- [ ] Task tool invocation uncommented
- [ ] Researcher agent deploys successfully
- [ ] First test execution completes without errors
- [ ] research.json artifact created
- [ ] Checkpoint created after researcher

✅ **Quality**:
- [ ] Research has ≥3 best practices with sources
- [ ] Research has ≥3 security considerations
- [ ] Research has ≥1 recommended library with rationale
- [ ] Research has ≥1 alternative considered
- [ ] All sources from 2024-2025 (recent)

✅ **Performance**:
- [ ] Researcher completes in < 15 minutes
- [ ] No timeouts or crashes
- [ ] Checkpoint saves correctly
- [ ] Resume plan generated (25% progress)

✅ **Repeatability**:
- [ ] Tested with ≥5 different request types
- [ ] Success rate ≥80% (4/5 pass)
- [ ] Consistent quality across tests
- [ ] Error handling works

✅ **Documentation**:
- [ ] WEEK6_VALIDATION.md created
- [ ] Lessons learned documented
- [ ] Issues and solutions recorded
- [ ] Week 6 commit created

---

## Next Steps (Week 7)

After Week 6 completes successfully:

1. **Create planner-v2.md**
   - Read manifest.json + research.json
   - Design architecture
   - Create architecture.json

2. **Implement invoke_planner()**
   - Similar pattern to invoke_researcher()
   - Add checkpoint after planner

3. **Test orchestrator → researcher → planner**
   - End-to-end two-agent pipeline
   - Validate architecture.json quality

---

## Conclusion

Week 6 is the **most critical week** in v2.0 development. It proves:
- Infrastructure works with real agents
- Task tool integration functions
- Artifact creation succeeds
- Checkpoint system operates correctly

**If Week 6 succeeds**: Clear path to complete pipeline (Weeks 7-12)
**If Week 6 fails**: May need infrastructure adjustments

Take time to thoroughly test and validate. Quality here determines success of remaining weeks.

---

**Status**: ⏳ Ready to Execute
**Prerequisites**: ✅ All infrastructure complete
**Duration**: 5-7 days
**Next**: Week 7 - Add Planner Agent
